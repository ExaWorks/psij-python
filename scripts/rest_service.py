#!/usr/bin/env python3

'''
This file implements a psij job service.  The service can be contacted via
a REST API.

the service will

Requests are formed as follows:

    {
        'cmd'   : str,
        'args'  : Tuple[Any],
        'kwargs': Dict[str, Any]
    }

Repsonse messages are formed as follows:

    {
        'err'   : str = None,  # error message
        'exc'   : str = None,  # exception stacktrace
        'res'   : Any          # any data type
    }

Note: interal data serialization relies on `msgbuf`, and all data types used for
      request and response messages MUST be serializable with `msgbuf`.


The service interface mirrors that of an psij executor implementation.  The
supported `cmd` requests, their parameters and return values are as follows:

    register_client(name: str = None, url: str = None) -> Tuple[str, str]

        name: name of backend psij executor to use for this client
              defaults to `local`
        url : url to pass to backend psij executor
              defaults to `fork://localhost/`

        The returned tuple contains two strings: `cid` and `sub_url`.

        cid    : unique ID to identify the client on further requests
        sub_url: zmq subscriber URL to subscribe for state notifications

        Register client, configure the service's psij executor to use for this
        client, and return a unique client ID.  That ID is required for
        all further requests.

        The returned `sub_url` will point to an additional ZMQ socket the server
        provides.  That socket is of `zmq.XBUB` type: the client can connect
        with an `zmq.SUB` socket and subscribe state notifications.  The topic
        to be used for that subscription is the returned `cid`.


    submit(cid: str, spec: Dict[str, Any]) -> str

        cid : client ID obtained via `register_client`
        spec: serialized psij.JobSepc

        This method submits a job as described by the JobSpec to the backend psij
        executor and returns the job ID.


    cancel(cid: str, jobid: str) -> None

        cid  : client ID obtained via `register_client`
        jobid: job ID obtained via `submit` or `list`

        This method will cancel the specified job.  The method returns without
        waiting for the cancelation request to suceed, the callee should observe
        state notifications to confirm successfull cancellation.


    list(cid: str) -> List[str]

        cid  : client ID obtained via `register_client`

        This method will return a list of job IDs known to this service.

'''


from fastapi import FastAPI, WebSocket, WebSocketDisconnect

import psij
import json
import queue
import asyncio
import logging
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
            name:str : name of psij executor to use
            url:str  : optional url to pass to psij executor

        returns:
            uid:str  : unique ID identifying the registered client
            addr:str : URL to be used for state notifications
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
app = FastAPI()
service = Service(app)


@app.get("/executor/{name}")
def register(name: str, url: Optional[str] = None) -> str:
    return service._request_register(name, url)


@app.put("/{cid}")
def submit(cid: str, spec: Dict[str, Any]) -> str:
    return service._request_submit(cid, spec)


@app.delete("/{cid}/{jobid}")
def cancel(cid: str, jobid: str) -> None:
    return service._request_cancel(cid, jobid)


@app.get("/{cid}/jobs")
def list_jobs(cid: str) -> List[str]:
    return service._request_list(cid)
