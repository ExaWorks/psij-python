import os
import threading
from typing import Type, Dict


class SingletonThread(threading.Thread):
    """
    A convenience class to return a thread that is guaranteed to be unique to this process.

    This is intended to work with fork() to ensure that each os.getpid() value is associated with
    at most one thread. This is not safe. The safe thing, as pointed out by the fork() man page,
    is to not use fork() with threads. However, this is here in an attempt to make it slightly
    safer for when users really really want to take the risk against all advice.
    """

    _instances: Dict[int, 'SingletonThread'] = {}
    _lock = threading.RLock()

    @classmethod
    def get_instance(cls: Type['SingletonThread']) -> 'SingletonThread':
        """Returns a started instance of this thread.

        The instance is guaranteed to be unique for this process. This method also guarantees
        that a forked process will get a separate instance of this thread from the parent.
        """
        with cls._lock:
            my_pid = os.getpid()
            if my_pid not in cls._instances:
                instance = cls()
                cls._instances[my_pid] = instance
                instance.start()
            return cls._instances[my_pid]
