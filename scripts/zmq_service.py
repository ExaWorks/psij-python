#!/usr/bin/env python3

import psij

import functools

import radical.utils as ru

from typing import List, Dict, Any


'''
This file implements a psij job service.  The service can be contacted via ZMQ.
It listens for requests on a `zmq.REP` reply socket - a client should
accordingly connect via an `zmq:REQ` request socket.

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
        'res'   : Any          # any serializable data type
    }


The service interface mirrors that of an psij executor implementation.  The
supported `cmd` requests, their parameters and return values are as follows:

    register_client(name: str = None, url: str = None) -> sid: str, sub_url: str

        name: name of backend psij executor to use for this client
              defaults to `local`
        url : url to pass to backend psij executor
              defaults to `fork://localhost/`


        sid    : unique ID to identify the client on further requests
        sub_url: zmq subscriber URL to subscribe for state notifications

        Register client, configure the service's psij executor to use for this
        client, and return a unique session ID.  That ID is required for
        all further requests.

        The returned `sub_url` will point to an additional ZMQ socket the server
        provides.  That socket is of `zmq.XBUB` type: the client can connect
        with an `zmq.SUB` socket and subscribe state notifications.  The topic
        to be used for that subscription is the returned `sid`.


    submit(sid: str, spec: Dict[str, Any]) -> str

        sid : session ID obtained via `register_client`
        spec: serialized psij.JobSepc

        This method submits a job as described by the JobSpec to the backend psij
        executor and returns the job ID.


    cancel(sid: str, jobid: str) -> None

        sid  : session ID obtained via `register_client`
        jobid: job ID obtained via `submit` or `list`

        This method will cancel the specified job.  The method returns without
        waiting for the cancelation request to suceed, the callee should observe
        state notifications to confirm successfull cancellation.


    list(sid: str) -> List[str]

        sid  : session ID obtained via `register_client`

        This method will return a list of job IDs known to this service.

'''


# ------------------------------------------------------------------------------
#
class Service(ru.zmq.Server):

    # --------------------------------------------------------------------------
    #
    def __init__(self):

        ru.zmq.Server.__init__(self, url='tcp://*:12345')

        self.register_request('register', self._request_register)
        self.register_request('submit', self._request_submit)
        self.register_request('cancel', self._request_cancel)
        self.register_request('list', self._request_list)

        self._clients = dict()

        self._deserialize = psij.Import()

        # run a pubsub bridge for state notifications
        self._pubsub = ru.zmq.PubSub({'channel': 'state',
                                      'log_lvl': 'debug'})
        self._pubsub.start()
        self._pub = ru.zmq.Publisher('state', self._pubsub.addr_pub)

    # --------------------------------------------------------------------------
    #
    def _status_callback(self, sid: str, job: psij.Job, status: psij.JobStatus):

        msg = {'jobid': job.id,
               'time': status.time,
               'message': status.message,
               'state': str(status.state),
               'metadata': status.metadata,
               'exit_code': status.exit_code}
        self._log.debug('status update for %s: %s', sid, msg)
        self._pub.put(sid, msg)

    # --------------------------------------------------------------------------
    #
    def _request_register(self, name: str, url: str = None) -> str:

        # register new client
        sid = ru.generate_id('client')

        if not url:
            # by default run jobs on localhost
            url = 'fork://localhost'

        # create executor
        jex = psij.JobExecutor.get_instance(name=name, url=url)

        # register state callback for this sid
        cb = functools.partial(self._status_callback, sid)
        jex.set_job_status_callback(cb)

        # store client information
        self._clients[sid] = {'jex': jex,
                              'jobs': dict()}

        # client is now known and initialized
        return sid, str(self._pubsub.addr_sub)

    # --------------------------------------------------------------------------
    #
    def _request_submit(self, sid: str, spec: Dict[str, Any]) -> str:

        if sid not in self._clients:
            raise ValueError('unknown client sid %s' % sid)

        job = psij.Job(self._deserialize.from_dict(spec, 'JobSpec'))
        self._clients[sid]['jobs'][job.id] = job
        self._clients[sid]['jex'].submit(job)

        return job.id

    # --------------------------------------------------------------------------
    #
    def _request_cancel(self, sid: str, jobid: str) -> None:

        if sid not in self._clients:
            raise ValueError('unknown client sid %s' % sid)

        if jobid not in self._clients[sid]['jobs']:
            raise ValueError('unknown job id %s' % jobid)

        jex = self._clients[sid]['jex']
        job = self._clients[sid]['jobs'][jobid]

        jex.cancel(job)

    # --------------------------------------------------------------------------
    #
    def _request_list(self, sid: str) -> List[str]:

        if sid not in self._clients:
            raise ValueError('unknown client sid %s' % sid)

        return list(self._clients[sid]['jobs'])

    # --------------------------------------------------------------------------
    #
    def _request_stage_in(self, data, fname):
        ...
        raise NotImplementedError()

    # --------------------------------------------------------------------------
    #
    def _request_stage_out(self, fname):
        ...
        raise NotImplementedError()


# ------------------------------------------------------------------------------
#
if __name__ == '__main__':

    s = Service()
    s.start()
    s.wait()

# ------------------------------------------------------------------------------
