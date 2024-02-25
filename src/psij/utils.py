import atexit
import io
import logging
import os
import random
import socket
import tempfile
import threading
import time
from pathlib import Path
from typing import Type, Dict, Optional, Tuple, Set, List

import psutil

from psij import JobExecutor, Job, JobState, JobStatus

logger = logging.getLogger(__name__)


class SingletonThread(threading.Thread):
    """
    A convenience class to return a thread that is guaranteed to be unique to this process.

    This is intended to work with fork() to ensure that each os.getpid() value is associated with
    at most one thread. This is not safe. The safe thing, as pointed out by the fork() man page,
    is to not use fork() with threads. However, this is here in an attempt to make it slightly
    safer for when users really really want to take the risk against all advice.

    This class is meant as an abstract class and should be used by subclassing and implementing
    the `run` method.
    """

    _instances: Dict[int, Dict[type, 'SingletonThread']] = {}
    _lock = threading.RLock()

    def __init__(self, name: Optional[str] = None, daemon: bool = False) -> None:
        """
        Instantiation of this class or one of its subclasses should be done through the
        :meth:`get_instance` method rather than directly.

        Parameters
        ----------
        name
            An optional name for this thread.
        daemon
            A daemon thread does not prevent the process from exiting.
        """
        super().__init__(name=name, daemon=daemon)

    @classmethod
    def get_instance(cls: Type['SingletonThread']) -> 'SingletonThread':
        """Returns a started instance of this thread.

        The instance is guaranteed to be unique for this process. This method also guarantees
        that a forked process will get a separate instance of this thread from the parent.
        """
        with cls._lock:
            my_pid = os.getpid()
            if my_pid in cls._instances:
                classes = cls._instances[my_pid]
            else:
                classes = {}
                cls._instances[my_pid] = classes
            if cls in classes:
                return classes[cls]
            else:
                instance = cls()
                classes[cls] = instance
                instance.start()
                return instance


class _StatusUpdater(SingletonThread):
    # we are expecting short messages in the form <jobid> <status>
    RECV_BUFSZ = 2048

    def __init__(self) -> None:
        super().__init__()
        self.name = 'Status Update Thread'
        self.daemon = True
        self.work_directory = Path.home() / '.psij'
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(True)
        self.socket.settimeout(0.5)
        self.socket.bind(('', 0))
        self.update_port = self.socket.getsockname()[1]
        self.ips = self._get_ips()
        logger.debug('Local IPs: %s' % self.ips)
        logger.debug('Status updater port: %s' % self.update_port)
        self._create_update_file()
        logger.debug('Update file: %s' % self.update_file.name)
        self.partial_file_data = ''
        self.partial_net_data = ''
        self._jobs: Dict[str, Tuple[Job, JobExecutor]] = {}
        self._jobs_lock = threading.RLock()
        self._sync_ids: Set[str] = set()
        self._last_received = ''

    def _get_ips(self) -> List[str]:
        addrs = psutil.net_if_addrs()
        r = []
        for name, l in addrs.items():
            if name == 'lo':
                continue
            for a in l:
                if a.family == socket.AddressFamily.AF_INET:
                    r.append(a.address)
        return r

    def _create_update_file(self) -> None:
        f = tempfile.NamedTemporaryFile(dir=self.work_directory, prefix='supd_', delete=False)
        name = f.name
        self.update_file_name = name
        atexit.register(os.remove, name)
        f.close()
        self.update_file = open(name, 'r+b')
        self.update_file.seek(0, io.SEEK_END)
        self.update_file_pos = self.update_file.tell()

    def register_job(self, job: Job, ex: JobExecutor) -> None:
        with self._jobs_lock:
            self._jobs[job.id] = (job, ex)

    def unregister_job(self, job: Job) -> None:
        with self._jobs_lock:
            try:
                del self._jobs[job.id]
            except KeyError:
                # There are cases when it's difficult to ensure that this method is only called
                # once for each job. Instead, ignore errors here, since the ultimate goal is to
                # remove the job from the _jobs dictionary.
                pass

    def step(self) -> None:
        self.update_file.seek(0, io.SEEK_END)
        pos = self.update_file.tell()
        if pos > self.update_file_pos:
            self.update_file.seek(self.update_file_pos, io.SEEK_SET)
            n = pos - self.update_file_pos
            self._process_update_data(self.update_file.read(n))
            self.update_file_pos = pos
        else:
            try:
                data = self.socket.recv(_StatusUpdater.RECV_BUFSZ)
                self._process_update_data(data)
            except TimeoutError:
                pass
            except socket.timeout:
                # before 3.10, this was a separate exception from TimeoutError
                pass
            except BlockingIOError:
                pass

    def run(self) -> None:
        while True:
            try:
                self.step()
            except Exception:
                logger.exception('Exception in status updater thread. Ignoring.')

    def flush(self) -> None:
        # Ensures that, upon return from this call, all updates available before this call have
        # been processed. To do so, we send a UDP packet to the socket to wake it up and wait until
        # it is received. This does not guarantee that file-based updates are necessarily
        # processes, since that depends on many factors.
        token = '_SYNC ' + str(random.getrandbits(128))
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(bytes(token, 'utf-8'), ('127.0.0.1', self.update_port))
        delay = 0.0001
        while token not in self._sync_ids:
            time.sleep(delay)
            delay *= 2

    def _process_update_data(self, data: bytes) -> None:
        sdata = data.decode('utf-8')
        if sdata == self._last_received:
            # we send UDP packets to all IP addresses of the submit host, which may
            # result in duplicates, so we drop consecutive messages that are identical
            return
        else:
            self._last_received = sdata
        lines = sdata.splitlines()
        for line in lines:
            if sdata.startswith('_SYNC '):
                self._sync_ids.add(sdata)
                continue
            els = line.split()
            if len(els) > 2 and els[1] == 'LOG':
                logger.info('%s %s' % (els[0], ' '.join(els[2:])))
                continue
            if len(els) != 2:
                logger.warning('Invalid status update message received: %s' % line)
                continue
            job_id = els[0]
            state = JobState.from_name(els[1])
            job = None
            with self._jobs_lock:
                try:
                    (job, executor) = self._jobs[job_id]
                except KeyError:
                    logger.debug('Received status updated for inexistent job with id %s' % job_id)
            if job:
                executor._set_job_status(job, JobStatus(state))
