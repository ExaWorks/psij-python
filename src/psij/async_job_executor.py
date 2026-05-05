import asyncio
import logging
from abc import abstractmethod
from asyncio import AbstractEventLoop
from datetime import timedelta
from typing import Optional, Dict, List, Type, Set, Union, Callable, Awaitable, Coroutine, Any, \
    TypeVar

from psij.job_executor import JobExecutor
from psij.base_job import BaseJob
from psij.job_spec import JobSpec
from psij.job import Job
from psij.job_state import JobState
from psij.exceptions import JobException, InvalidJobException
from psij.job_status import JobStatus
from psij._base_executor import BaseExecutor
from psij.async_job import AsyncJob, AsyncJobStatusCallback, AsyncFunctionJobStatusCallback
from psij.descriptor import Descriptor, _VersionEntry
from psij._plugins import _register_plugin, _print_plugin_status
from psij.job_executor_config import JobExecutorConfig


logger = logging.getLogger(__name__)

T = TypeVar('T')


class AsyncJobExecutor(BaseExecutor):
    """An abstract base class for all AsyncJobExecutor implementations."""

    _executors: Dict[str, List[_VersionEntry[BaseExecutor]]] = {}

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
        super().__init__(url, config)
        # _cb is not thread-safe; changing it while jobs are running could lead to badness
        self._cb: Optional[AsyncJobStatusCallback] = None

    @abstractmethod
    async def submit(self, job: AsyncJob) -> None:
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

    async def run(self, job: AsyncJob) -> None:
        """
        A convenience method to submit and wait for a job to complete.

        Parameters
        ----------
        job
            The job to run.
        """
        await self.submit(job)
        status = await job.wait()
        assert status is not None
        if status.state == JobState.FAILED:
            raise JobException(status.message, status.exit_code)

    @abstractmethod
    async def cancel(self, job: AsyncJob) -> None:
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
    async def list(self) -> List[str]:
        """List native IDs of all jobs known to the backend.

        This method is meant to return a list of native IDs for jobs submitted to the backend
        by any means, not necessarily through this executor or through PSI/J.
        """
        pass

    @abstractmethod
    async def attach(self, job: AsyncJob, native_id: str) -> None:
        """
        Attaches a job to a native job.

        :param job: A job to attach. The job must be in the :attr:`~psij.JobState.NEW` state.
        :param native_id: The native ID to attach to as returned by :attr:`~psij.BaseJob.native_id`.
        """
        pass

    async def set_job_status_callback(self, cb: Union[AsyncJobStatusCallback,
                                      Callable[[AsyncJob, JobStatus],
                                               Awaitable[None]]]) -> None:
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
        if isinstance(cb, AsyncJobStatusCallback):
            self._cb = cb
        else:
            self._cb = AsyncFunctionJobStatusCallback(cb)

    def run_coroutine(self, c: Coroutine[Any, Any, T], loop: AbstractEventLoop) -> T:
        """Starts a coroutine in the asyncio loop that the executor was created in.

        Parameters
        ----------
        coro
            The coroutine to start.
        """
        try:
            task = asyncio.run_coroutine_threadsafe(c, loop)
            return task.result()
        except Exception as ex:
            logger.warning('Error running coroutine.', exc_info=ex)
            raise

    async def disconnect(self, validity: Optional[timedelta] = None) -> str:
        """
        Suspends the connection to the service while maintaining the session.

        For details, see :meth:`~psij.JobExecutor.disconnect`.
        """
        return '<sessionid>'

    def reconnect(self, session: str) -> None:
        """
        Reconnects to a previously suspended session.

        For details, see :meth:`~psij.JobExecutor.reconnect`.
        """
        pass

    async def _set_job_status(self, job: AsyncJob, status: JobStatus) -> None:
        await job.set_status(status)

    async def _notify_callback(self, job: AsyncJob, status: JobStatus) -> None:
        if self._cb:
            try:
                await self._cb.job_status_changed(job, status)
            except Exception as ex:
                logger.warning('Job status callback for %s threw an exception:',
                               job.id, exc_info=ex)

    def __str__(self) -> str:
        """Returns a string representation of this executor."""
        if self.url is not None:
            return 'AsyncJobExecutor[{}, {}, url={}]'.format(getattr(self.__class__, '_NAME_'),
                                                             getattr(self.__class__, '_VERSION_'),
                                                             self.url)
        else:
            return 'AsyncJobExecutor[{}, {}]'.format(getattr(self.__class__, '_NAME_'),
                                                     getattr(self.__class__, '_VERSION_'))

    @staticmethod
    def get_instance(name: str, version_constraint: Optional[str] = None,
                     url: Optional[str] = None,
                     config: Optional[JobExecutorConfig] = None,
                     use_wrapper: Optional[bool] = False) -> 'AsyncJobExecutor':
        """
        Returns an instance of an `AsyncJobExecutor`.

        :param name: The name of the executor to return. This must be one of the values returned
            by :func:`~psij.JobExecutor.get_executor_names`. If the value of the `name` parameter
            is not one of the valid values returned by
            :func:`~psij.JobExecutor.get_executor_names`, `ValueError` is raised.
        :param version_constraint: A version constraint for the executor in the form
            '(' <op> <version>[, <op> <version[, ...]] ')', such as "( > 0.0.2, != 0.0.4)".
        :param url: An optional URL to pass to the `JobExecutor` instance.
        :param config: An optional configuration to pass to the instance.
        :return: An AsyncJobExecutor.
        """
        # might want to cache these instances if url and config match
        try:
            exec = BaseExecutor._get_instance(name, version_constraint, url, config,
                                              False, AsyncJobExecutor._executors)
        except ValueError as ex:
            if use_wrapper:
                try:
                    from psij._async import AsyncExecutorWrapper
                    sync_exec = JobExecutor.get_instance(name, version_constraint, url, config)
                    exec = AsyncExecutorWrapper(sync_exec)
                except ValueError:
                    raise ValueError from ex
            else:
                raise
        assert isinstance(exec, AsyncJobExecutor)
        return exec

    @staticmethod
    def register_executor(desc: Descriptor, root: str) -> None:
        """
        Registers an `AsyncJobExecutor` class through a :class:`~psij.descriptor.Descriptor`.

        The class can then be later instantiated using :func:`~psij.AsyncJobExecutor.get_instance`.

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
        _register_plugin(desc, root, 'async-executor', AsyncJobExecutor._executors)

    @staticmethod
    def _print_plugin_status() -> None:
        _print_plugin_status(AsyncJobExecutor._executors, 'async-executor')

    @staticmethod
    def _check_cls_attr(ecls: Type['AsyncJobExecutor'], attr: str, name: str) -> None:
        if not hasattr(ecls, attr):
            raise ValueError('Class {} is missing the executor {} attribute, "{}"'.
                             format(ecls, name, attr))

    @staticmethod
    def get_executor_names() -> Set[str]:
        """
        Returns a set of registered executor names.

        Names returned by this method can be passed to :func:`~psij.AsyncJobExecutor.get_instance`
        as the `name` parameter.

        Returns
        -------
        A set of async executor names corresponding to the known executors.
        """
        return set(AsyncJobExecutor._executors.keys())

    def _check_job(self, job: BaseJob) -> JobSpec:
        if isinstance(job, Job):
            raise InvalidJobException('Async executors cannot handle Job instances. '
                                      'Please use AsyncJob.')
        return super()._check_job(job)
