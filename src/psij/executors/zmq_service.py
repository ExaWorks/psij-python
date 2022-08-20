"""This module contains the ZMQService :class:`~psij.JobExecutor`.
"""

import time
from typing import Optional, List

from psij import (
    Job,
    JobExecutorConfig,
    JobState,
    JobStatus,
    JobExecutor,
    Export,
)

import radical.utils as ru


class ZMQServiceJobExecutor(JobExecutor):
    """A :class:`~psij.JobExecutor` for a PSI/J ZMQ service endpoint.

    This executor forwards all requests to a ZMQ service endpoint which is then
    executing the respective request on the target resource.
    """

    _state_map = {'NEW': JobState.NEW,
                  'QUEUED': JobState.QUEUED,
                  'ACTIVE': JobState.ACTIVE,
                  'COMPLETED': JobState.COMPLETED,
                  'FAILED': JobState.FAILED,
                  'CANCELED': JobState.CANCELED}
    _final = [JobState.COMPLETED, JobState.FAILED, JobState.CANCELED]

    def __init__(
        self, url: Optional[str] = None, config: Optional[JobExecutorConfig] = None
    ) -> None:
        """
        Initializes a `ZMQServiceJobExecutor`.

        :param url: Not used, but required by the spec for automatic initialization.
        :param config: The `ZMQServiceJobExecutor` does not have any configuration options.
        """
        if not url.startswith('tcp://'):
            raise ValueError('expected `tcp://` url')
        super().__init__(url=url, config=config if config else JobExecutorConfig())
        self._client = ru.zmq.Client(url=url)
        self._jobs = dict()
        self._idmap = dict()
        self._serialize = Export()

        self._sid = self._client.request('register', name='local')
        pubsub_url = self._client.request('get_pubsub', sid=self._sid)
        ru.zmq.Subscriber(channel='state', url=pubsub_url,
                          cb=self._state_cb, topic=self._sid)

    def _state_cb(self, topic, msg):
        """Callback triggered on job state updates

        Update the status of the psij.Job.
        """
        jobid = self._idmap.get(msg['jobid'])
        job = self._jobs.get(jobid)
        if not job:
            # FIXME: use logger
            print('job %s unknown: %s' % (jobid, self._jobs.keys()))
            return

        state = self._state_map[msg['state']]
        status = JobStatus(state, time=msg['time'], message=msg['message'],
                           exit_code=msg['exit_code'], metadata=msg['metadata'])
        self._set_job_status(job, status)

        if state in self._final:
            del self._jobs[jobid]

    def submit(self, job: Job) -> None:
        """See :func:`~psij.job_executor.JobExecutor.submit`."""
        job.executor = self
        self._jobs[job.id] = job
        job._native_id = self._client.request('submit', sid=self._sid,
                                              spec=self._serialize.to_dict(job.spec))
        self._idmap[job._native_id] = job.id

    def cancel(self, job: Job) -> None:
        """See :func:`~psij.job_executor.JobExecutor.cancel`."""
        self._client.request('cancel', sid=self._sid, jobid=job._native_id)

    def list(self) -> List[str]:
        """See :func:`~psij.job_executor.JobExecutor.list`.

        Return a list of ids representing jobs that are running on the
        underlying implementation - in this case Flux job IDs.

        :return: The list of known tasks.
        """
        return self._client.request('list', sid=self._sid)

    def attach(self, job: Job, native_id: str) -> None:
        """
        Attaches a job to a process.

        The job must be in the :attr:`~psij.JobState.NEW` state.

        :param job: The job to attach.
        :param native_id: The native ID of the process to attached to, as
          obtained through :func:`~psij.executors.flux.FluxJobExecutor.list` method.
        """
        job.executor = self
        job._native_id = native_id
        self._idmap[native_id] = job.id
        self._jobs[job.id] = job
        return self._client.request('attach', sid=self._sid, native_id=native_id)
