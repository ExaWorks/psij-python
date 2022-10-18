"""This module contains the ZMQService :class:`~psij.JobExecutor`.
"""

import threading
from typing import Optional, List, Dict, Any

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

        :param url: address at which to contact the remote service.
                    Supported schemas: `tcp://` and `zmq://`
        :param config: The `ZMQServiceJobExecutor` does not have any
                    configuration options.
        """
        ru_url = ru.Url(url)
        if ru_url.schema not in ['tcp', 'zmq']:
            raise ValueError('expected `tcp://` or `zmq://` as url schema')
        if ru_url.schema == 'zmq':
            ru_url.schema = 'tcp'
        if not config:
            config = JobExecutorConfig()

        if ru_url.path and ru_url.path != '/':
            name = ru_url.path.strip('/')
            ru_url.path = None
        else:
            name = 'local'
        super().__init__(url=str(ru_url), config=config)

        self._jobs: Dict[str, Job] = dict()
        self._idmap: Dict[str, str] = dict()
        self._serialize = Export()

        # we can only update the idmap when the `submit` request returns, but
        # an state notification may happen before that.  We use a lock to ensure
        # that state updates are delayed until after `submit` completed.
        self._lock = threading.Lock()

        # connect to service and register this client instance
        self._client = ru.zmq.Client(url=str(ru_url).rstrip('/'))
        self._cid, sub_url = self._client.request('register', name=name)

        # subscribe for state update information (trigger `self._state_cb`)
        self._sub = ru.zmq.Subscriber(channel='state', url=sub_url,
                                      cb=self._state_cb, topic=self._cid)

    def __del__(self) -> None:
        self._sub.stop()

    def _state_cb(self, topic: str, msg: Dict[str, Any]) -> None:
        """Callback triggered on job state update messages

        Update the status of the psij.Job.
        """
        assert topic == self._cid, str([topic, self._cid, msg])

        with self._lock:
            jobid = self._idmap.get(msg['jobid'])
            if not jobid:
                # FIXME: use logger
                print('job %s unknown: %s' % (jobid, self._idmap.keys()))
                return

        job = self._jobs.get(jobid)
        assert job

        state = self._state_map[msg['state']]
        status = JobStatus(state, time=msg['time'], message=msg['message'],
                           exit_code=msg['exit_code'], metadata=msg['metadata'])
        self._set_job_status(job, status)

        if state in self._final:
            del self._jobs[jobid]

    def submit(self, job: Job) -> None:
        """See :func:`~psij.job_executor.JobExecutor.submit`."""
        job.executor = self
        with self._lock:
            self._jobs[job.id] = job
            job._native_id = str(self._client.request('submit', cid=self._cid,
                                                      spec=self._serialize.to_dict(job.spec)))
            self._idmap[job._native_id] = job.id

    def cancel(self, job: Job) -> None:
        """See :func:`~psij.job_executor.JobExecutor.cancel`."""
        self._client.request('cancel', cid=self._cid, jobid=job._native_id)

    def list(self) -> List[str]:
        """See :func:`~psij.job_executor.JobExecutor.list`.

        Return a list of ids representing jobs that are running on the
        underlying implementation.  We consider the remote service's job ids as
        native job ids and return them unaltered.

        :return: The list of known job ids.
        """
        ret = list()
        for val in self._client.request('list', cid=self._cid):
            ret.append(str(val))
        return ret

    def attach(self, job: Job, native_id: str) -> None:
        """
        Attaches a job instance to an existing job

        The job instance must be in the :attr:`~psij.JobState.NEW` state.

        :param job: The job instance to attach.
        :param native_id: The native ID of the backend job to attached to, as
          obtained through the `:func:list` method.
        """
        assert job.status.state == JobState.NEW
        job.executor = self
        job._native_id = native_id
        self._idmap[native_id] = job.id
        self._jobs[job.id] = job
