#!/usr/bin/env python3

'''
This file implements a psij job service.  The service can be contacted via
a REST API.

the service will

The service interface mirrors that of an psij executor implementation.  The
supported `cmd` requests, their parameters and return values are as follows:

    register_client(name: str = None) -> str

        REST: GET /executor/{name}/
        name: name of backend psij executor to use for this client
              defaults to `local`

        returns: a unique ID to identify the client on further requests.

        Register client, configure the service's psij executor to use for this
        client, and return a unique client ID.  That ID is required for
        all further requests.


    submit(cid: str, spec: Dict[str, Any]) -> str

        REST: PUT /{cid}/
        cid : client ID obtained via `register_client`
        spec: serialized psij.JobSepc

        This method submits a job as described by the JobSpec to the backend psij
        executor and returns the job ID.


    cancel(cid: str, jobid: str) -> None

        REST : DELETE /{cid}/{jobid}
        cid  : client ID obtained via `register_client`
        jobid: job ID obtained via `submit` or `list`

        This method will cancel the specified job.  The method returns without
        waiting for the cancelation request to suceed, the callee should observe
        state notifications to confirm successfull cancellation.


    list(cid: str) -> List[str]

        REST: GET /{cid}/jobs
        cid : client ID obtained via `register_client`

        This method will return a list of job IDs known to this service.

    FIXME:
      - use cookie instead of client id
      - add authorization and authentication
      - add data staging
'''


from fastapi import FastAPI, WebSocket, WebSocketDisconnect

import psij
import queue
import asyncio
import logging
import uvicorn
import functools

from typing import List, Dict, Any, Optional


# ------------------------------------------------------------------------------
#
class _Client(object):

    def __init__(self, jex: psij.JobExecutor):

        self.jex: psij.JobExecutor = jex
        self._jobs: Dict[str, psij.Job] = dict()
        self.ws: Optional[WebSocket] = None
        self._queue: queue.Queue = queue.Queue()

    def add_job(self, job: psij.Job) -> None:

        self._jobs[job.id] = job

    def get_job(self, jobid: str) -> Optional[psij.Job]:

        return self._jobs.get(jobid)

    def list_jobs(self) -> List[str]:

        return list(self._jobs.keys())

    def get_msg(self) -> Any:
        try:
            return self._queue.get_nowait()
        except Exception:
            pass

    def send(self, msg: Any) -> None:
        self._queue.put(msg)


# ------------------------------------------------------------------------------
#
class Service(object):

    def __init__(self, app: FastAPI) -> None:

        self._clients: Dict[str, _Client] = dict()
        self._deserialize = psij.Import()
        self._log = logging.getLogger('psij')
        self._cnt: int = 0

        # ----------------------------------------------------------------------
        # websocket endpoint at which client can regoister for state updates
        @app.websocket("/ws/{cid}")
        async def ws_endpoint(ws: WebSocket, cid: str) -> None:

            await ws.accept()

            client = self._clients.get(cid)
            if not client:
                self._log.error("refuse ws for %s" % cid)
                raise ValueError("unknown client cid %s" % cid)

            self._log.info("accept ws for %s" % cid)
            try:
                # keep this async task alive as long as there are messages to
                # send and the websocket is alive
                while True:
                    msg = client.get_msg()
                    if msg:
                        await ws.send_json(msg)
                    else:
                        await asyncio.sleep(0.1)

            except WebSocketDisconnect:
                self._log.info("dropped ws for %s" % cid)
        # ----------------------------------------------------------------------

    def _status_callback(self, cid: str, job: psij.Job, status: psij.JobStatus) -> None:

        client = self._clients.get(cid)
        if not client:
            print("unknown client cid %s" % cid)
            return

        msg = {'jobid': job.id,
               'time': status.time,
               'message': status.message,
               'state': str(status.state),
               'metadata': status.metadata,
               'exit_code': status.exit_code}
        self._log.debug('cb: %s: %s', cid, msg)
        client.send(msg)

    def _request_register(self, name: str, url: Optional[str] = None) -> str:
        '''
        parameters:
            name:str: name of psij executor to use
            url:str: optional URL to be passed to backend executor

        returns:
            str: unique ID identifying the registered client
        '''

        # register new client
        cid = 'client.%04d' % self._cnt
        self._cnt += 1

        # create executor
        jex = psij.JobExecutor.get_instance(name=name, url=url)

        # register state callback for this cid
        cb = functools.partial(self._status_callback, cid)
        jex.set_job_status_callback(cb)

        # store client information
        self._clients[cid] = _Client(jex)

        # client is now known and initialized
        return cid

    def _request_submit(self, cid: str, spec: Dict[str, Any]) -> str:
        '''
        parameters:
           cid:str   : client ID
           spec:Dict : job spec

        returns:
           jobid:str : psij job ID for submitted job
        '''

        client = self._clients.get(cid)
        if not client:
            raise ValueError('unknown client cid %s' % cid)

        job = psij.Job(self._deserialize.from_dict(spec, 'JobSpec'))
        client.add_job(job)
        client.jex.submit(job)

        return job.id

    def _request_cancel(self, cid: str, jobid: str) -> None:
        '''
        parameters:
           cid:str   : client ID
           jobid:str : psij job ID for job to be canceled
        '''

        client = self._clients.get(cid)
        if not client:
            raise ValueError('unknown client cid %s' % cid)

        job = client.get_job(jobid)
        if not job:
            raise ValueError('unknown job id %s' % jobid)

        client.jex.cancel(job)

    def _request_list(self, cid: str) -> List[str]:
        '''
        parameters:
           cid:str   : client ID

        returns:
           jobids:List[str] : all known psij job IDs
        '''

        client = self._clients.get(cid)
        if not client:
            raise ValueError('unknown client cid %s' % cid)

        return client.list_jobs()

    def _request_stage_in(self, data: str, fname: str) -> None:

        with open(fname, 'w') as fout:
            fout.write(data)

    def _request_stage_out(self, fname: str) -> str:

        with open(fname) as fin:
            return fin.read()


# ------------------------------------------------------------------------------
#
if __name__ == '__main__':

    app = FastAPI()
    service = Service(app)

    @app.get("/executor/{name}")
    def register(name: str, url: Optional[str] = None) -> str:
        """
        Register a new client and create an executor of type 'name'.
        request: GET /executor/{name}/
            name: type of executor to create for this client
            url: optional url to pass to the backend executor
        response: a new client ID (str)
        """

        return service._request_register(name, url)

    @app.put("/{cid}")
    def submit(cid: str, spec: Dict[str, Any]) -> str:
        """
        Submit a job.
        request: PUT /{cid}/
            cid: client ID as obtained by `register`
            data: json serialized `psij.JobSpec` dictionary
        response: a new job ID (str) for the submitted job
        """
        return service._request_submit(cid, spec)

    @app.delete("/{cid}/{jobid}")
    def cancel(cid: str, jobid: str) -> None:
        """
        Cancel a job.
        request: DELETE /{cid}/{jobid}
            cid: client ID as obtained by `register`
            jobid: ID of job to be canceled
        response: None
        """
        return service._request_cancel(cid, jobid)

    @app.get("/{cid}/jobs")
    def list_jobs(cid: str) -> List[str]:
        """
        List all known jobs.
        request: GET /{cid}/jobs
            cid: client ID as obtained by `register`
        response: serialized json string containing a list of job IDs (`List[str]`)
        """
        return service._request_list(cid)

    uvicorn.run(app, port=8000, access_log=False)
