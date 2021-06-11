"""This module contains the RP :class:`~psi.j.JobExecutor`."""

import time
import logging

from typing import Any, Optional, List, Tuple, Dict

from distutils.version import StrictVersion

from psi.j import InvalidJobException, SubmitException
from psi.j import Job, JobExecutorConfig, JobState, JobStatus, JobSpec
from psi.j import JobExecutor

logger = logging.getLogger(__name__)


class RPJobExecutor(JobExecutor):
    """
    A job executor that runs jobs via radical.pilot.
    """

    import radical.pilot as _rp

    _NAME_ = 'rp'
    _VERSION_ = StrictVersion('0.0.1')

    _state_map = {_rp.NEW: JobState.NEW,
                  _rp.TMGR_STAGING_INPUT_PENDING: JobState.QUEUED,
                  _rp.AGENT_EXECUTING: JobState.ACTIVE,
                  _rp.DONE: JobState.COMPLETED,
                  _rp.FAILED: JobState.FAILED,
                  _rp.CANCELED: JobState.CANCELED}

    def __init__(self, url: Optional[str] = None,
                 config: Optional[JobExecutorConfig] = None) -> None:
        """
        Initializes a `RPJobExecutor`.

        :param url: Not used, but required by the spec for automatic initialization.
        :param config: The `RPJobExecutor` does not have any configuration options.
        :type config: psi.j.JobExecutorConfig
        """
        # TODO: url is not passed
        # if not url.startswith('rp://'):
        #     raise ValueError('expected `rp://` url')

        super().__init__(url=url, config=config)
        self._session = self._rp.Session()
        self._pmgr = self._rp.PilotManager(session=self._session)
        self._tmgr = self._rp.TaskManager(session=self._session)

        self._pmgr.register_callback(self._pilot_state_cb)
        self._tmgr.register_callback(self._task_state_cb)

        pd = self._rp.PilotDescription({'resource': 'local.localhost',
                                        'cores': 32,
                                        'runtime': 15})
        self._pilot = self._pmgr.submit_pilots(pd)
        self._tmgr.add_pilots(self._pilot)
        self._tasks: Dict[str, Tuple[Any, Any]] = dict()

    def _pilot_state_cb(self, pilot: _rp.Pilot, rp_state: str) -> None:

        logger.info('pilot %s: %s', pilot.uid, pilot.state)

    def _task_state_cb(self, task: _rp.Task, rp_state: str) -> None:

        jpsi_uid = task.name
        jpsi_job = self._tasks[jpsi_uid][0]

        ec = None
        if task.state in self._rp.FINAL:
            ec = task.exit_code

        old_state = jpsi_job.status.state
        new_state = self._state_map.get(task.state)

        logger.debug('%s --> %s - %s', jpsi_uid, task.state, new_state)

        if new_state is None:
            # not an interesting state transition, ignore
            return

        if old_state == new_state:
            return

        metadata = {'nativeId': task.uid}

        if ec:
            metadata['exit_code'] = ec

        if task.state in self._rp.FINAL:
            metadata['final'] = True

        status = JobStatus(new_state, time=time.time(),
                           metadata=metadata)
        self._update_job_status(jpsi_job, status)

    def submit(self, job: Job) -> None:
        """
        Submits the specified :class:`~psi.j.Job` to the pilot.

        Successful return of this method indicates that the job has been
        submitted to RP and all changes in the job status, including failures,
        are reported using notifications. If the job specification is invalid,
        an :class:`~psi.j.InvalidJobException` is thrown. If the actual
        submission fails for reasons outside the validity of the job,
        a :class:`~psi.j.SubmitException` is thrown.

        :param job: The job to be submitted.
        """
        spec = job.spec
        if not spec:
            raise InvalidJobException('Missing specification')

        try:
            td = self._job_2_descr(job)
            task = self._tmgr.submit_tasks(td)
            self._tasks[job.id] = (job, task)

        except Exception as ex:
            raise SubmitException('Failed to submit job') from ex

    def _job_2_descr(self, job: Job) -> Dict[str, Any]:

        # TODO: use resource spec
        # TODO: use meta data for jpsi uid

        spec: Optional[JobSpec] = job.spec

        if not spec:
            raise InvalidJobException('Missing specification')

        from_dict: Dict[str, Any] = {'name': job.id,
                                     'executable': spec.executable,
                                     'arguments': spec.arguments or [],
                                     'environment': spec.environment or {},
                                     'stdout': spec.stdout_path or '',
                                     'stderr': spec.stderr_path or '',
                                     'sandbox': spec.directory or ''}

        return self._rp.TaskDescription(from_dict=from_dict)

    def cancel(self, job: Job) -> None:
        """
        Cancels a job.

        :param job: The job to cancel.
        """
        with job._status_cv:
            if job.status.state == JobState.NEW:
                job._set_status(JobStatus(JobState.CANCELED))
                return

        if job.id not in self._tasks:
            raise ValueError('job not known')

        _, task = self._tasks[job.id]

        self._tmgr.cancel_tasks(uids=task.uid)

    def list(self) -> List[str]:
        """
        Return a list of ids representing jobs that are running on the
        underlying implementation - in this case RP task IDs.

        :return: The list of known tasks.
        """

        return [str(uid) for uid in self._tmgr.list_tasks()]

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

        task = self._tmgr.get_tasks(uids=[native_id])[0]
        self._tasks[job.id] = (job, task)

        state = self._state_map[task.state]
        self._update_job_status(job, JobStatus(state, time=time.time()))

    def _update_job_status(self, job: Job, job_status: JobStatus) -> None:

        job._set_status(job_status, self)
        if self._cb:
            self._cb.job_status_changed(job, job_status)


__PSI_J_EXECUTORS__ = [RPJobExecutor]
