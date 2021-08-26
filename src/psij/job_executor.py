import inspect
from abc import ABC, abstractmethod
from bisect import bisect_left
from distutils.version import Version
from distutils.versionpredicate import VersionPredicate
from threading import RLock
from typing import Optional, Dict, List, Type, cast, Union, Callable, Set

import psij
from psij.job import Job, JobStatusCallback
from psij.job_executor_config import JobExecutorConfig
from psij.launchers.launcher import Launcher


class _VersionEntry:
    def __init__(self, version: Version, ecls: Type['JobExecutor']) -> None:
        self.version = version
        self.ecls = ecls

    def __cmp__(self, other: '_VersionEntry') -> int:
        if self.version == other.version:
            return 0
        elif self.version < other.version:
            return -1
        else:
            return 1

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, _VersionEntry)
        return self.version == other.version

    def __lt__(self, other: object) -> bool:
        assert isinstance(other, _VersionEntry)
        return self.version < other.version

    def __gt__(self, other: object) -> bool:
        assert isinstance(other, _VersionEntry)
        return self.version > other.version


class JobExecutor(ABC):
    """This is an abstract base class for all JobExecutor implementations."""

    _executors = {}  # type: Dict[str, List[_VersionEntry]]

    def __init__(self, url: Optional[str] = None, config: Optional[JobExecutorConfig] = None):
        """
        Initializes this executor using an optional `url` and an optional configuration.

        :param url: The URL is a string that a `JobExecutor` implementation can interpret as the
            location of a backend.
        :param config: An optional configuration specific to each `JobExecutor` implementation.
        """
        self.url = url
        self.config = config
        # _cb is not thread-safe; changing it while jobs are running could lead to badness
        self._cb = None  # type: Optional[JobStatusCallback]
        self._launchers_lock = RLock()
        self._launchers = {}  # type: Dict[str, Launcher]

    @property
    def name(self) -> str:
        """Returns the name of this executor."""
        return cast(str, getattr(self.__class__, '_NAME_'))

    @property
    def version(self) -> Version:
        """Returns the version of this executor."""
        return cast(Version, getattr(self.__class__, '_VERSION_'))

    @abstractmethod
    def submit(self, job: Job) -> None:
        """
        Submits a Job to the underlying implementation.

        Successful return of this method indicates that the job has been sent to the underlying
        implementation and all changes in the job status, including failures, are reported using
        notifications. Conversely, if one of the two possible exceptions is thrown, then the job
        has not been successfully sent to the underlying implementation, the job status remains
        unchanged, and no status notifications about the job will be fired.

        :raises ~psij.InvalidJobException: Thrown if the job specification cannot be understood.
            This exception is fatal in that submitting another job with the exact same details will
            also fail with an `~psij.InvalidJobException`. In principle, the underlying
            implementation / LRM is the entity ultimately responsible for interpreting a
            specification and reporting any errors associated with it. However, in many cases, this
            reporting may come after a significant delay. In the interest of failing fast, library
            implementations should make an effort of validating specifications early and throwing
            this exception as soon as possible if that validation fails.

        :raises ~psij.SubmitException: Thrown if the request cannot be sent to the underlying
            implementation. Unlike `~psij.InvalidJobException`, this exception can occur for
            reasons that are transient.
        """
        pass

    @abstractmethod
    def cancel(self, job: Job) -> None:
        """
        Cancels a job that has been submitted to underlying executor implementation.

        A successful return of this method only indicates that the request for cancelation has been
        communicated to the underlying implementation. The job will then be canceled at the
        discretion of the implementation, which may be at some later time. A successful
        cancelation is reflected in a change of status of the respective job to
        :attr:`~psij.JobState.CANCELED`. User code can synchronously wait until the
        :attr:`~psij.JobState.CANCELED` state is reached using `job.wait(JobState.CANCELED)` or
        even `job.wait()`, since the latter would wait for all final states, including
        `JobState.CANCELED`. In fact, it is recommended that `job.wait()` be used because it is
        entirely possible for the job to complete before the cancelation is communicated to the
        underlying implementation and before the client code receives the completion notification.
        In such a case, the job will never enter the `CANCELED` state and
        `job.wait(JobState.CANCELED)` would hang indefinitely.

        :param job: The job to be canceled.
        """
        pass

    @abstractmethod
    def list(self) -> List[str]:
        """List native IDs of all jobs known to the backend."""
        pass

    @abstractmethod
    def attach(self, job: Job, native_id: str) -> None:
        """
        Attaches a job to a native job.

        :param job: A job to attach. The job must be in the :attr:`~psij.JobState.NEW` state.
        :param native_id: The native ID to attach to as returned by :attr:`~psij.Job.native_id`.
        """
        pass

    def set_job_status_callback(self,
                                cb: Union[JobStatusCallback,
                                          Callable[[Job, 'psij.JobStatus'], None]]) -> None:
        """
        Registers a status callback with this executor.

        The callback can either be a subclass of :class:`~psij.JobStatusCallback` or a function
        accepting two arguments: a :class:`~psij.Job` and a :class:`~psij.JobStatus` and
        returning nothing.

        The callback will be invoked whenever a status change occurs for any of the jobs submitted
        to this job executor, whether they were submitted with an individual job status callback or
        not. To remove the callback, set it to `None`.

        :param cb: An instance of :class:`~psij.JobStatusCallback` or a function with two
            parameters, job of type :class:`~psij.Job` and job_status of type
            :class:`~psij.JobStatus` returning nothing.
        """
        if isinstance(cb, JobStatusCallback):
            self._cb = cb
        else:
            self._cb = _FunctionJobStatusCallback(cb)

    def __str__(self) -> str:
        """Returns a string representation of this executor."""
        if self.url is not None:
            return 'JobExecutor[{}, {}, url={}]'.format(getattr(self.__class__, '_NAME_'),
                                                        getattr(self.__class__, '_VERSION_'),
                                                        self.url)
        else:
            return 'JobExecutor[{}, {}]'.format(getattr(self.__class__, '_NAME_'),
                                                getattr(self.__class__, '_VERSION_'))

    @staticmethod
    def get_instance(name: str, version_constraint: Optional[str] = None, url: Optional[str] = None,
                     config: Optional[JobExecutorConfig] = None) -> 'JobExecutor':
        """
        Returns an instance of a `JobExecutor`.

        :param name: The name of the executor to return. This must be one of the values returned
            by :func:`~psij.JobExecutor.get_executor_names`. If the value of the `name` parameter
            is not one of the valid values returned by
            :func:`~psij.JobExecutor.get_executor_names`, `ValueError` is raised.
        :param version_constraint: A version constraint for the executor in the form
            '(' <op> <version>[, <op> <version[, ...]] ')', such as "( > 0.0.2, != 0.0.4)".
        :param url: An optional URL to pass to the `JobExecutor` instance.
        :param config: An optional configuration to pass to the instance.
        :return: A JobExecutor.
        """
        # might want to cache these instances if url and config match
        if name not in JobExecutor._executors:
            raise ValueError('No such executor "{}"'.format(name))
        versions = JobExecutor._executors[name]
        ecls = None  # type: Optional[Type[JobExecutor]]
        if version_constraint:
            pred = VersionPredicate('x(' + version_constraint + ')')
            for entry in reversed(versions):
                if pred.satisfied_by(entry.version):
                    ecls = entry.ecls
        else:
            ecls = versions[-1].ecls

        if ecls is None:
            raise ValueError('No executor "{}" found to satisfy "{}"'.format(name,
                                                                             version_constraint))
        else:
            return ecls(url=url, config=config)

    @staticmethod
    def register_executor(ecls: Type['JobExecutor']) -> None:
        """
        Registers a `JobExecutor` class.

        The class can then be later instantiated using :func:`~psij.JobExecutor.get_instance`.

        :param ecls: A subclass of `JobExecutor` to register. The class must have the `_NAME_` and
            `_VERSION_` class attributes which define the name and version of the `JobExecutor` and
            should match the values returned by the `name` and `version` properties of instances
            of `ecls`.
        """
        # mypy uses the base class to infer that some arguments are missing; however, the actual
        # executors are such that they allow nullary construction
        JobExecutor._check_cls_attr(ecls, '_NAME_', 'name')
        JobExecutor._check_cls_attr(ecls, '_VERSION_', 'version')

        name = cast(str, getattr(ecls, '_NAME_'))
        version = cast(Version, getattr(ecls, '_VERSION_'))

        if name not in JobExecutor._executors:
            JobExecutor._executors[name] = []
        existing = JobExecutor._executors[name]
        entry = _VersionEntry(version, ecls)
        # check if an executor with this version already exists
        index = bisect_left(existing, entry)
        if index != len(existing) and existing[index].version == version:
            p1 = inspect.getfile(existing[index].ecls)
            p2 = inspect.getfile(ecls)
            if p1 == p2:
                # can happen if PYTHONPATH has, e.g., a/, a/b/, so ignore silently
                return
            raise ValueError(('An executor by the name "{}" with version {} is already '
                              'registered. Existing path: {}; current path: {}').format(name,
                                                                                        version,
                                                                                        p1, p2))
        existing.insert(index, entry)

    def _update_job_status(self, job: Job, job_status: 'psij.JobStatus') -> None:
        job._set_status(job_status, self)
        if self._cb:
            self._cb.job_status_changed(job, job_status)

    @staticmethod
    def _check_cls_attr(ecls: Type['JobExecutor'], attr: str, name: str) -> None:
        if not hasattr(ecls, attr):
            raise ValueError('Class {} is missing the executor {} attribute, "{}"'.
                             format(ecls, name, attr))

    @staticmethod
    def get_executor_names() -> Set[str]:
        """
        Returns the names of registered executors.

        Names returned by this method can be passed to :func:`~psij.JobExecutor.get_instance` as
        the `name` parameter.

        Returns
        -------
        A set of executor names corresponding to the known executors.
        """
        return set(JobExecutor._executors.keys())

    def _get_launcher(self, name: str) -> Launcher:
        with self._launchers_lock:
            if name not in self._launchers:
                self._launchers[name] = Launcher.get_instance(name, self.config)
            return self._launchers[name]


class _FunctionJobStatusCallback(JobStatusCallback):
    """A JobStatusCallback that wraps a function."""

    def __init__(self, fn: Callable[[Job, 'psij.JobStatus'], None]):
        """Initializes a `_FunctionJobStatusCallback`."""
        self.fn = fn

    def job_status_changed(self, job: Job, job_status: 'psij.JobStatus') -> None:
        """See :func:`~psij.JobStatusCallback.job_status_changed`."""
        self.fn(job, job_status)
