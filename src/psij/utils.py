import os
import threading
from typing import Type, Dict, Optional


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

    _instances: Dict[int, 'SingletonThread'] = {}
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
            if my_pid not in cls._instances:
                instance = cls()
                cls._instances[my_pid] = instance
                instance.start()
            return cls._instances[my_pid]
