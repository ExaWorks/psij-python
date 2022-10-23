"""This module contains the RestService :class:`~psij.JobExecutor`."""

import json
import requests
import websocket
import threading

from urllib.parse import urlparse, urlunparse

from typing import Optional, List, Dict

from psij import (
    Job,
    JobExecutorConfig,
    JobState,
    JobStatus,
    JobExecutor,
    Export,
)


class RestServiceJobExecutor(JobExecutor):
    """A :class:`~psij.JobExecutor` for a PSI/J Rest service endpoint.

    This executor forwards all requests to a Rest service endpoint which is then
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
        Initializes a `RestServiceJobExecutor`.

        :param url: address at which to contact the remote service.
                    Supported schemas: `http://` and `https://`
        :param config: The `RestServiceJobExecutor` does not have any
                    configuration options.
        """
        if not config:
            config = JobExecutorConfig()

        if not url:
            url = 'http://localhost:8000'

        url_obj = urlparse(url)

        if url_obj.scheme not in ['http', 'https']:
            raise ValueError('expected `http://` or `https://` as url schema')

        if url_obj.path and url_obj.path != '/':
            name = url_obj.path.strip('/')
        else:
            name = 'local'

        url = urlunparse(url_obj._replace(path=''))

        super().__init__(url=str(url), config=config)

        self._jobs: Dict[str, Job] = dict()
        self._idmap: Dict[str, str] = dict()
        self._serialize = Export()

        # we can only update the idmap when the `submit` request returns, but
        # an state notification may happen before that.  We use a lock to ensure
        # that state updates are delayed until after `submit` completed.
        self._lock = threading.Lock()

        # connect to service and register this client instance
        self._cid = str(requests.get('%s/executor/%s' % (url, name)).json())

        # create a daemong thread for websocket state notifications
        t = threading.Thread(target=self._state_listener)
        t.daemon = True
        t.start()

    def __del__(self) -> None:
        """Stop websocket thread upon destruction."""
        ...

    def _state_listener(self) -> None:
        """thrtead to listen for on job state update messages on the websocket.

        Update the status of the psij.Job.
        """
        if 'http://' in self.url:
            ws_url = self.url.replace('http://', 'ws://')
        else:
            ws_url = self.url.replace('http://', 'ws://')

        assert ws_url.startswith('ws://')

        ws = websocket.create_connection(ws_url + '/ws/' + self._cid)
        while True:
            msg = json.loads(ws.recv())

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
            spec = self._serialize.to_dict(job.spec)
            rep = requests.put('%s/%s' % (self.url, self._cid), json=spec)
            job._native_id = str(rep.json())
            self._idmap[job._native_id] = job.id

    def cancel(self, job: Job) -> None:
        """See :func:`~psij.job_executor.JobExecutor.cancel`."""
        requests.delete('%s/%s/%s' % (self.url, self._cid, job._native_id))

    def list(self) -> List[str]:
        """See :func:`~psij.job_executor.JobExecutor.list`.

        Return a list of ids representing jobs that are running on the
        underlying implementation.  We consider the remote service's job ids as
        native job ids and return them unaltered.

        :return: The list of known job ids.
        """
        rep = requests.get('%s/%s/jobs' % (self.url, self._cid))
        return rep.json()

    def attach(self, job: Job, native_id: str) -> None:
        """
        Attaches a job instance to an existing job.

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
