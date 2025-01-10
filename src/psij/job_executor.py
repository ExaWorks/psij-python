import logging
from abc import ABC, abstractmethod
from packaging.version import Version
from threading import RLock
from typing import Optional, Dict, List, Type, cast, Union, Callable, Set

import psij
from psij import InvalidJobException
from psij.descriptor import Descriptor, _VersionEntry
from psij._plugins import _register_plugin, _get_plugin_class, _print_plugin_status
from psij.job_state import JobState
from psij.job_status import JobStatus
from psij.job import Job, JobStatusCallback, FunctionJobStatusCallback
from psij.job_executor_config import JobExecutorConfig
from psij.job_launcher import Launcher
from psij.job_spec import JobSpec
from psij.resource_spec import ResourceSpecV1


logger = logging.getLogger(__name__)


_DEFAULT_RESOURCES = ResourceSpecV1()


class JobExecutor(ABC):
    """An abstract base class for all JobExecutor implementations."""

    _executors: Dict[str, List[_VersionEntry['JobExecutor']]] = {}

    def __init__(self, url: Optional[str] = None,
                 config: Optional[JobExecutorConfig] = None):
        """
        :param url: The URL is a string that a `JobExecutor` implementation can interpret as the
            location of a backend.
        :param config: An configuration specific to each `JobExecutor` implementation. This
            parameter is marked as optional such that concrete `JobExecutor` classes can be
            instantiated with no `config` parameter. However, concrete `JobExecutor` classes
            must pass a default configuration up the inheritance tree and ensure that the
            `config` parameter of the ABC constructor is non-null.
        """
        self.url = url
        assert config
        self.config = config
        # _cb is not thread-safe; changing it while jobs are running could lead to badness
        self._cb: Optional[JobStatusCallback] = None
        self._launchers_lock = RLock()
        self._launchers: Dict[str, Launcher] = {}

    @property
    def name(self) -> str:
        """Returns the name of this executor."""
        # The _NAME_ class attribute is set by the instantiation mechanism. This is only done to
        # avoid name duplication/matching issues (name defined by the descriptor vs. name defined
        # statically by a pre-set _NAME_attribute), but is not otherwise necessary to do so. In
        # other words, one could very well return a static value here and ensure that the
        # descriptor has the same name for this class.
        return cast(str, getattr(self.__class__, '_NAME_'))

    @property
    def version(self) -> Version:
        """Returns the version of this executor."""
        return cast(Version, getattr(self.__class__, '_VERSION_'))

    def _check_job(self, job: Job) -> JobSpec:
        """
        Checks a job for consistency and correctness.

        Verifies that various aspects of the job are correctly specified. This includes precisely
        the following checks:
        * the job has a non-null specification
        * job.spec.environment is a Dict[str, [str | int]]

        While this method makes a fair attempt at ensuring the validity of the job, it makes no
        such guarantees. Specifically, if an executor implementation requires checks not listed
        above, it should implement them explicitly.

        These checks are meant to trigger common runtime type errors somewhat early and with clear
        error messages. In production software, these checks can be disabled by invoking Python
        with one of the optimization flags (`-O` or `-OO`).

        Upon completion, this method sets the :attr:`~psij.Job.executor` attribute of the job and
        returns the job specification.

        Parameters
        ----------
        job
            The job to validate

        Returns
        -------
            A non-null job specification
        """
        if job.status.state != JobState.NEW:
            raise InvalidJobException('Job must be in NEW state')
        spec = job.spec
        if not spec:
            raise InvalidJobException('Missing specification')
        if not spec.resources:
            spec.resources = _DEFAULT_RESOURCES

        if __debug__:
            if spec.environment is not None:
                for k, v in spec.environment.items():
                    if not isinstance(k, str):
                        raise TypeError('environment key "%s" is not a string (%s)'
                                        % (k, type(k).__name__))
                    if not isinstance(v, (str, int)):
                        raise TypeError('environment value for key "%s" must be string '
                                        'or int type (%s)' % (k, type(v).__name__))

        if job.executor is not None:
            raise InvalidJobException('Job is already associated with an executor')
        job.executor = self
        return spec

    @abstractmethod
    def submit(self, job: Job) -> None:
        """
        Submits a Job to the underlying implementation.

        Successful return of this method indicates that the job has been sent to the underlying
        implementation and all changes in the job status, including failures, are reported using
        notifications. Conversely, if one of the two possible exceptions is thrown, then the job
        has not been successfully sent to the underlying implementation, the job status remains
        unchanged, and no status notifications about the job will be fired.

        A successful return of this method guarantees that the job's `native_id` property is set.

        :raises InvalidJobException: Thrown if the job specification cannot be understood.
            This exception is fatal in that submitting another job with the exact same details will
            also fail with an `InvalidJobException`. In principle, the underlying
            implementation / LRM is the entity ultimately responsible for interpreting a
            specification and reporting any errors associated with it. However, in many cases, this
            reporting may come after a significant delay. In the interest of failing fast, library
            implementations should make an effort of validating specifications early and throwing
            this exception as soon as possible if that validation fails.

        :raises SubmitException: Thrown if the request cannot be sent to the underlying
            implementation. Unlike `InvalidJobException`, this exception can occur for
            reasons that are transient.
        """
        pass

    @abstractmethod
    def cancel(self, job: Job) -> None:
        """
        Cancels a job that has been submitted to underlying executor implementation.

        A successful return of this method only indicates that the request for cancellation has been
        communicated to the underlying implementation. The job will then be canceled at the
        discretion of the implementation, which may be at some later time. A successful
        cancellation is reflected in a change of status of the respective job to
        :attr:`~psij.JobState.CANCELED`. User code can synchronously wait until the
        :attr:`~psij.JobState.CANCELED` state is reached using `job.wait(JobState.CANCELED)` or
        even `job.wait()`, since the latter would wait for all final states, including
        `JobState.CANCELED`. In fact, it is recommended that `job.wait()` be used because it is
        entirely possible for the job to complete before the cancellation is communicated to the
        underlying implementation and before the client code receives the completion notification.
        In such a case, the job will never enter the `CANCELED` state and
        `job.wait(JobState.CANCELED)` would hang indefinitely.

        :param job: The job to be canceled.

        :raises SubmitException: Thrown if the request cannot be sent to the underlying
            implementation.
        """
        pass

    @abstractmethod
    def list(self) -> List[str]:
        """List native IDs of all jobs known to the backend.

        This method is meant to return a list of native IDs for jobs submitted to the backend
        by any means, not necessarily through this executor or through PSI/J.
        """
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

        The callback can either be a subclass of :class:`~psij.job.JobStatusCallback` or a
        procedure accepting two arguments: a :class:`~psij.Job` and a :class:`~psij.JobStatus`.

        The callback will be invoked whenever a status change occurs for any of the jobs submitted
        to this job executor, whether they were submitted with an individual job status callback or
        not. To remove the callback, set it to `None`.

        :param cb: An instance of :class:`~psij.job.JobStatusCallback` or a callable with two
            parameters: job of type :class:`~psij.Job` and job_status of type
            :class:`~psij.JobStatus`.
        """
        if isinstance(cb, JobStatusCallback):
            self._cb = cb
        else:
            self._cb = FunctionJobStatusCallback(cb)

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
        selected = _get_plugin_class(name, version_constraint, 'executor', JobExecutor._executors)

        assert selected.ecls is not None
        assert issubclass(selected.ecls, JobExecutor)
        setattr(selected.ecls, '_NAME_', name)
        setattr(selected.ecls, '_VERSION_', selected.version)
        instance = selected.ecls(url=url, config=config)
        return instance

    @staticmethod
    def register_executor(desc: Descriptor, root: str) -> None:
        """
        Registers a `JobExecutor` class through a :class:`~psij.descriptor.Descriptor`.

        The class can then be later instantiated using :func:`~psij.JobExecutor.get_instance`.

        Parameters
        ----------
        desc
            A :class:`~psij.descriptor.Descriptor` with information about the executor to
            be registered.
        root
            A filesystem path under which the implementation of the executor is to be loaded from.
            Executors from other locations, even if under the correct package, will not be
            registered by this method. If an executor implementation is only available under a
            different root path, this method will throw an exception.
        """
        _register_plugin(desc, root, 'executor', JobExecutor._executors)

    @staticmethod
    def _print_plugin_status() -> None:
        _print_plugin_status(JobExecutor._executors, 'executor')

    @staticmethod
    def _check_cls_attr(ecls: Type['JobExecutor'], attr: str, name: str) -> None:
        if not hasattr(ecls, attr):
            raise ValueError('Class {} is missing the executor {} attribute, "{}"'.
                             format(ecls, name, attr))

    @staticmethod
    def get_executor_names() -> Set[str]:
        """
        Returns a set of registered executor names.

        Names returned by this method can be passed to :func:`~psij.JobExecutor.get_instance` as
        the `name` parameter.

        Returns
        -------
        A set of executor names corresponding to the known executors.
        """
        return set(JobExecutor._executors.keys())

    def _get_launcher(self, name: str, version_constraint: Optional[str] = None) -> Launcher:
        with self._launchers_lock:
            if name not in self._launchers:
                self._launchers[name] = Launcher.get_instance(name,
                                                              version_constraint=version_constraint,
                                                              config=self.config)
            return self._launchers[name]

    def _set_job_status(self, job: Job, status: JobStatus) -> None:
        try:
            job.status = status
        except Exception as ex:
            logger.warning('Failed to set status for job %s: %s', job.id, ex)

    def _notify_callback(self, job: Job, status: JobStatus) -> None:
        if self._cb:
            try:
                self._cb.job_status_changed(job, status)
            except Exception as ex:
                logger.warning('Job status callback for %s threw an exception: %s', job.id, ex)
