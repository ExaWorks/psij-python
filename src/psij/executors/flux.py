"""This module contains the Flux :class:`~psij.JobExecutor`.

Implementation references:
github.com/flux-framework/flux-core/blob/master/src/bindings/python/flux/job/executor.py
flux-framework.readthedocs.io/projects/flux-core/en/latest/python/job_submission.html#the-fluxexecutor-interface

Events and state transitions:
github.com/flux-framework/rfc/blob/master/spec_21.rst
"""

import time
import copy
import warnings
import concurrent.futures
from functools import partial
from typing import Any, Optional, Dict, List

from psij import (
    Job,
    JobExecutorConfig,
    JobState,
    JobStatus,
    JobExecutor,
    InvalidJobException,
    ResourceSpec,
    ResourceSpecV1,
)

import flux
import flux.job


class FluxJobExecutor(JobExecutor):
    """A :class:`~psij.JobExecutor` for the Flux scheduler.

    The `Flux resource manager framework <http://flux-framework.org/>`_ is
    deployed and used on a per-user basis at many sites, and is slated to become
    the system-level resource manager at LLNL.

    Uses Flux's python library/bindings to submit, monitor, and manipulate jobs.
    """

    _event_map = {
        # 'submit': JobState.QUEUED,
        # 'alloc': None,
        "start": JobState.ACTIVE,
        # 'finish': JobState.COMPLETED,
        # 'release': None,
        # 'free': None,
        # 'clean': None,
        # 'exception': JobState.FAILED
    }

    def __init__(
        self, url: Optional[str] = None, config: Optional[JobExecutorConfig] = None
    ) -> None:
        """
        :param url: Not used, but required by the spec for automatic initialization.
        :param config: The `FluxJobExecutor` does not have any configuration options.
        """
        # TODO: url is not passed
        # if not url.startswith('flux://'):
        #     raise ValueError('expected `flux://` url')
        super().__init__(url=url, config=config if config else JobExecutorConfig())
        self._flux_executor = flux.job.FluxExecutor()
        self._fh = flux.Flux()
        self._futures: Dict[Job, flux.job.FluxExecutorFuture] = {}

    def _jobid_cb(self, job: Job, fut: flux.job.FluxExecutorFuture) -> None:
        """Callback triggered when Flux jobid is ready.

        Fetch the jobid, set it on the psij.Job, and set the the job to QUEUED.
        """
        job._native_id = fut.jobid()
        job_status = JobStatus(JobState.QUEUED, time=time.time())
        self._set_job_status(job, job_status)

    def _event_cb(self, job: Job, fut: flux.job.FluxExecutorFuture, evt: Any) -> None:
        """Callback triggered when Flux job logs an event.

        Update the status of the psij.Job.
        """
        jpsi_state = self._event_map[evt.name]
        metadata = copy.deepcopy(evt.context)
        job_status = JobStatus(jpsi_state, time=time.time(), metadata=metadata)
        self._set_job_status(job, job_status)

    def _done_cb(self, job: Job, fut: flux.job.FluxExecutorFuture) -> None:
        """Callback triggered when Flux job completes.

        Fetch returncode or exception message and update the psij.Job.
        """
        try:
            returncode = fut.result()
        except concurrent.futures.CancelledError:
            status = JobStatus(JobState.CANCELED, time=time.time())
        except Exception as exc:
            if "type=cancel" in str(exc):
                state = JobState.CANCELED
            else:
                state = JobState.FAILED
            status = JobStatus(state, time=time.time(), message=str(exc))
        else:
            if returncode == 0:
                status = JobStatus(JobState.COMPLETED, time=time.time())
            else:
                status = JobStatus(
                    JobState.FAILED, time=time.time(), exit_code=returncode
                )
        self._set_job_status(job, status)
        # remove future from cache
        del self._futures[job]

    def _add_flux_callbacks(self, job: Job, fut: flux.job.FluxExecutorFuture) -> None:
        """Add jobid, event, and done callbacks to a Flux future."""
        fut.add_jobid_callback(partial(self._jobid_cb, job))
        for event in self._event_map.keys():
            fut.add_event_callback(event, partial(self._event_cb, job))
        fut.add_done_callback(partial(self._done_cb, job))
        # add future to cache
        self._futures[job] = fut

    def submit(self, job: Job) -> None:
        """See :func:`~psij.job_executor.JobExecutor.submit`."""
        spec = self._check_job(job)

        assert spec.attributes
        if isinstance(spec.resources, ResourceSpecV1):
            resources = spec.resources
        elif isinstance(spec.resources, ResourceSpec):
            raise InvalidJobException(
                f"ResourceSpec version {spec.resources.version} not supported"
            )
        else:
            resources = ResourceSpecV1(process_count=1, cpu_cores_per_process=1)
        if resources.exclusive_node_use:
            warnings.warn(
                "Flux does not support exclusive_node_use=True, ignoring...",
                UserWarning,
            )
        if resources.processes_per_node:
            raise InvalidJobException("Flux does not support processes_per_node")
        if not spec.executable:
            raise InvalidJobException("Job must have an executable")
        argv = list(spec.arguments) if spec.arguments else []
        argv.insert(0, spec.executable)
        flux_jobspec = flux.job.JobspecV1.from_command(
            argv,
            num_tasks=resources.process_count,
            cores_per_task=resources.cpu_cores_per_process,
            gpus_per_task=resources.gpu_cores_per_process,
            num_nodes=resources.node_count,
        )
        if spec.stdout_path:
            flux_jobspec.stdout = spec.stdout_path
        if spec.stdin_path:
            flux_jobspec.stdin = spec.stdin_path
        if spec.stderr_path:
            flux_jobspec.stderr = spec.stderr_path
        flux_jobspec.duration = spec.attributes.duration.total_seconds()
        fut = self._flux_executor.submit(flux_jobspec)
        self._add_flux_callbacks(job, fut)

    def cancel(self, job: Job) -> None:
        """See :func:`~psij.job_executor.JobExecutor.cancel`."""
        fut = self._futures[job]
        if not fut.cancel():
            flux.job.cancel_async(self._fh, fut.jobid())

    def list(self) -> List[str]:
        """See :func:`~psij.job_executor.JobExecutor.list`.

        Return a list of ids representing jobs that are running on the
        underlying implementation - in this case Flux job IDs.

        :return: The list of known tasks.
        """
        return [
            x["id"]
            for x in flux.job.job_list(
                self._fh,
                max_entries=100000,
                attrs=[],
                states=flux.constants.FLUX_JOB_STATE_ACTIVE,
            ).get()["jobs"]
        ]

    def attach(self, job: Job, native_id: str) -> None:
        """
        Attaches a job to a process.

        The job must be in the :attr:`~psij.JobState.NEW` state.

        :param job: The job to attach.
        :param native_id: The native ID of the process to attached to, as
          obtained through :func:`~psij.executors.flux.FluxJobExecutor.list` method.
        """
        job.executor = self
        self._add_flux_callbacks(job, self._flux_executor.attach(native_id))
