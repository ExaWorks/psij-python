#!/usr/bin/env python3

import psij

import functools

import radical.utils as ru


# ------------------------------------------------------------------------------
#
class Service(ru.zmq.Server):

    # --------------------------------------------------------------------------
    #
    def __init__(self):

        ru.zmq.Server.__init__(self, url='tcp://*:12345')

        self.register_request('register', self._request_register)
        self.register_request('get_pubsub', self._request_get_pubsub)
        self.register_request('submit', self._request_submit)
        self.register_request('cancel', self._request_cancel)
        self.register_request('list', self._request_list)
        self.register_request('attach', self._request_attach)

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
        self._pub.put(sid, msg)

    # --------------------------------------------------------------------------
    #
    def _request_register(self, name: str, url: str = None):

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
        return sid

    # --------------------------------------------------------------------------
    #
    def _request_get_pubsub(self, sid):

        if sid not in self._clients:
            raise ValueError('unknown client sid %s' % sid)

        return str(self._pubsub.addr_sub)

    # --------------------------------------------------------------------------
    #
    def _request_submit(self, sid, spec):

        if sid not in self._clients:
            raise ValueError('unknown client sid %s' % sid)

        spec = self._deserialize.from_dict(spec, 'JobSpec')
        job = psij.Job(spec)
        self._clients[sid]['jobs'][job.id] = job
        self._clients[sid]['jex'].submit(job)

        return job.id

    # --------------------------------------------------------------------------
    #
    def _request_cancel(self, sid, jobid):

        if sid not in self._clients:
            raise ValueError('unknown client sid %s' % sid)

        if jobid not in self._clients[sid]['jobs']:
            raise ValueError('unknown job id %s' % jobid)

        jex = self._clients[sid]['jex']
        job = self._clients[sid]['jobs'][jobid]

        jex.cancel(job)

    # --------------------------------------------------------------------------
    #
    def _request_list(self, sid):

        if sid not in self._clients:
            raise ValueError('unknown client sid %s' % sid)

        return list(self._clients[sid]['jobs'])

    # --------------------------------------------------------------------------
    #
    def _request_attach(self, sid):

        if sid not in self._clients:
            raise ValueError('unknown client sid %s' % sid)

        # FIXME: TBD
        raise NotImplementedError()

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
