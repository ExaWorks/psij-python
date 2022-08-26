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

    register_client(name: str = None, url: str = None) -> cid: str, sub_url: str

        name: name of backend psij executor to use for this client
              defaults to `local`
        url : url to pass to backend psij executor
              defaults to `fork://localhost/`


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
    def _status_callback(self, cid: str, job: psij.Job, status: psij.JobStatus):

        msg = {'jobid': job.id,
               'time': status.time,
               'message': status.message,
               'state': str(status.state),
               'metadata': status.metadata,
               'exit_code': status.exit_code}
        self._log.debug('status update for %s: %s', cid, msg)
        self._pub.put(cid, msg)

    # --------------------------------------------------------------------------
    #
    def _request_register(self, name: str, url: str = None) -> str:
        '''
        parameters:
            name:str : name of psij executor to use
            url:str  : optional url to pass to psij executor

        returns:
            uid:str  : unique ID identifying the registered client
            addr:str : URL to be used for state notifications
        '''

        # register new client
        cid = ru.generate_id('client')

        if not url:
            # by default run jobs on localhost
            url = 'fork://localhost'

        # create executor
        jex = psij.JobExecutor.get_instance(name=name, url=url)

        # register state callback for this cid
        cb = functools.partial(self._status_callback, cid)
        jex.set_job_status_callback(cb)

        # store client information
        self._clients[cid] = {'jex': jex,
                              'jobs': dict()}

        # client is now known and initialized
        return cid, str(self._pubsub.addr_sub)

    # --------------------------------------------------------------------------
    #
    def _request_submit(self, cid: str, spec: Dict[str, Any]) -> str:
        '''
        parameters:
           cid:str   : client ID
           spec:Dict : job spec

        returns:
           jobid:str : psij job ID for submitted job
        '''


        if cid not in self._clients:
            raise ValueError('unknown client cid %s' % cid)

        job = psij.Job(self._deserialize.from_dict(spec, 'JobSpec'))
        self._clients[cid]['jobs'][job.id] = job
        self._clients[cid]['jex'].submit(job)

        return job.id

    # --------------------------------------------------------------------------
    #
    def _request_cancel(self, cid: str, jobid: str) -> None:
        '''
        parameters:
           cid:str   : client ID
           jobid:str : psij job ID for job to be canceled
        '''

        if cid not in self._clients:
            raise ValueError('unknown client cid %s' % cid)

        if jobid not in self._clients[cid]['jobs']:
            raise ValueError('unknown job id %s' % jobid)

        jex = self._clients[cid]['jex']
        job = self._clients[cid]['jobs'][jobid]

        jex.cancel(job)

    # --------------------------------------------------------------------------
    #
    def _request_list(self, cid: str) -> List[str]:
        '''
        parameters:
           cid:str   : client ID

        returns:
           jobids:List[str] : all known psij job IDs
        '''

        if cid not in self._clients:
            raise ValueError('unknown client cid %s' % cid)

        return list(self._clients[cid]['jobs'])

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
