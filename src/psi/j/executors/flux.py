"""This module contains the Flux :class:`~psi.j.JobExecutor`."""

from __future__ import annotations

import time
import logging
import copy
import json
import threading
from functools import partial

from typing import Any, Optional, Dict

from distutils.version import StrictVersion

from psi.j import InvalidJobException
from psi.j import Job, JobExecutorConfig, JobState, JobStatus, JobAttributes
from psi.j import JobExecutor, ResourceSpecV1

logger = logging.getLogger(__name__)
# logging.basicConfig(level='DEBUG', force=True, filename='flux_connector.log')


class FluxJobExecutor(JobExecutor):
    """
    A job executor that runs jobs via Flux.
    """

    import radical.utils as _ru
    import flux as _flux

    _NAME_ = 'flux'
    _VERSION_ = StrictVersion('0.0.1')

    # map flux states to jpsi states.
    _state_map = {'NEW': JobState.QUEUED,
                  'DEPEND': None,
                  'SCHED': None,
                  'RUN': JobState.ACTIVE,
                  'CLEANUP': None,
                  'INACTIVE': JobState.COMPLETED}
    _event_map = {'submit': JobState.QUEUED,
                  # 'alloc': None,
                  'start': JobState.ACTIVE,
                  'finish': JobState.COMPLETED,
                  # 'release': None,
                  # 'free': None,
                  # 'clean': None,
                  'exception': JobState.FAILED}

    def __init__(self, url: Optional[str] = None,
                 config: Optional[JobExecutorConfig] = None) -> None:
        """
        Initializes a `FluxJobExecutor`.

        :param url: Not used, but required by the spec for automatic initialization.
        :param config: The `FluxJobExecutor` does not have any configuration options.
        :type config: psi.j.JobExecutorConfig
        """
        # TODO: url is not passed
        # if not url.startswith('flux://'):
        #     raise ValueError('expected `flux://` url')

        super().__init__(url=url, config=config)

        self._jobs = dict()  # {job.uid: [job, fut, flux_id]}
        self._idmap = dict()  # {flux_id, job.uid}
        self._lock = threading.RLock()  # lock state updates

        self._fh = self._ru.FluxHelper()
        self._finfo = self._fh.start_service()
        self._fuid = self._finfo['uid']
        self._fex = self._fh.get_executor(self._fuid)
        self._fh = self._fh.get_handle(self._fuid)

    # # TODO: how to free resources?
    # def close(self) -> None:
    #     try:
    #         if self._fh and self._fuid:
    #             self._fh.close_service(self._fuid)
    #     except Exception:
    #         pass

    def _jobid_cb(self, fut: Any, jpsi_id: str) -> None:

        jpsi_job, _ = self._jobs[jpsi_id]
        flux_id = fut.jobid()

        # From James Corbett: You can rely on the jobid callback always firing
        #       first. As Flux's bindings are now, FluxExecutor has to get the
        #       jobid before it can even request event updates, and the executor
        #       triggers the jobid callbacks before requesting event updates.
        #       [...] I don't think it would change unless there were fairly
        #       radical changes to the underlying Flux functions.
        logger.debug('register flux jobid for %s: %s', jpsi_id, flux_id)

        self._idmap[flux_id] = jpsi_id

        jpsi_job._native_id = flux_id
        job_status = JobStatus(JobState.QUEUED, time=time.time())
        self._update_job_status(jpsi_job, job_status)

    def _event_cb(self, fut: Any, evt: Any) -> None:

        flux_id = fut.jobid()
        jpsi_id = self._idmap.get(flux_id)
        jpsi_state = self._event_map[evt.name]

        if not jpsi_id:
            raise RuntimeError('event cb before jobid cb: %s', jpsi_id)

        if jpsi_id not in self._jobs:
            logger.error('event for unknown job: %s: %s - %s',
                         jpsi_id, jpsi_state, evt.context)
            return

        jpsi_job, flux_fut = self._jobs[jpsi_id]

        # on final state, attempt to obtain exit code
        metadata = copy.deepcopy(evt.context)
        exit_code = None
        if jpsi_state.final:
            exit_code = evt.context.get('status')
            if exit_code:
                exit_code = int(exit_code)

        if exit_code:
            jpsi_state = JobState.FAILED

        # `exception` events may have error messages (`note`) attached
        metadata['exit_code'] = exit_code
        metadata['message'] = metadata.get('note')
        job_status = JobStatus(jpsi_state, time=time.time(), metadata=metadata)
        self._update_job_status(jpsi_job, job_status)

    def submit(self, job: Job) -> None:

        with self._lock:

            # derive Flux job spec and submit them

            flux_spec = self._job_2_descr(job)

            # submit the job, register resulting future
            flux_fut = self._fex.submit(json.dumps(flux_spec))
            self._jobs[job.id] = [job, flux_fut]

            # asynchroneously wait for the flux jobid
            jobid_cb = partial(self._jobid_cb, jpsi_id=job.id)
            flux_fut.add_jobid_callback(jobid_cb)

            # register for event updates
            for ev in self._event_map:
                flux_fut.add_event_callback(ev, self._event_cb)

    def _job_2_descr(self, job: Job) -> Dict[str, Any]:
        jspec = job.spec

        # FIXME: what is spec, what is spec.attributes?
        # TODO: why don't we get job.attributes default values here?
        # TODO: why don't we get job.resources default values here?
        #
        if jspec.attributes is None:
            jspec.attributes = JobAttributes()

        if jspec.resources is None:
            jspec.resources = ResourceSpecV1(process_count=1,
                                             processes_per_node=1,
                                             cpu_cores_per_process=1,
                                             gpu_cores_per_process=1,
                                             exclusive_node_use=True)
        if not jspec.executable:
            raise InvalidJobException('no executable defined')

        if not jspec.arguments:
            jspec.arguments = []

        rspec = jspec.resources
        attr = jspec.attributes

        flux_spec = {
            "tasks": [{
                "slot": "task",
                "count": {
                    "per_slot": 1
                },
                "command": [jspec.executable] + jspec.arguments
            }],
            "attributes": {
                "system": {
                    # FIXME: flux hangs on `None` values
                    # "cwd": jspec.directory,
                    "duration": attr.duration.total_seconds()
                }
            },
            "version": 1,
            "resources": [{
                "count": rspec.process_count,
                "type": "slot",
                "label": "task",
                "with": [{
                    "count": rspec.cpu_cores_per_process,
                    "type": "core"
                }, {
                    "count": rspec.gpu_cores_per_process,
                    "type": "gpu"
                }]
            }]
        }

        return flux_spec

    def cancel(self, job: Job) -> None:

        flux_fut = self._jobs[job.id][1]
        flux_fut.cancel()

        _, flux_fut = self._jobs[job.id]
        flux_id = flux_fut.jobid()
        self._flux.job.cancel_async(self._fh, flux_id)

        job_status = JobStatus(JobState.CANCELED, time=time.time())
        self._update_job_status(job, job_status)

    def list(self):
        """
        Return a list of ids representing jobs that are running on the
        underlying implementation - in this case Flux job IDs.

        :return: The list of known tasks.
        """

        with self._lock:
            ret = self._flux.job.job_list(self._fh)
            return [x['id'] for x in ret]

    def attach(self, job: Job, native_id: str) -> None:
        """
        Attaches a job to a process.

        The job must be in the :attr:`~psi.j.JobState.NEW` state.

        :param job: The job to attach.
        :param native_id: The native ID of the process to attached to, as
        obtained through :func:`~psi.j.executors.RPJobExecutor.list` method.
        """

        if job.status.state != JobState.NEW:
            raise InvalidJobException('Job must be in the NEW state')

        task = self._tmgr.get_tasks(uids=native_id)
        self._jobs[job.id] = [job, task]

        state = self._state_map[task.state]
        self._update_job_status(job, JobStatus(state, time=time.time()))

    def _update_job_status(self, job: Job, job_status: JobStatus) -> None:

        job._set_status(job_status, self)
        if self._cb:
            self._cb.job_status_changed(job, job_status)


__PSI_J_EXECUTORS__ = [FluxJobExecutor]

