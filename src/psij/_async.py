import asyncio
from asyncio import AbstractEventLoop
from datetime import timedelta
from packaging.version import Version
from threading import Thread
from typing import Optional, Union, Callable, List, Sequence, Dict, Awaitable, Coroutine, Any
from typing import TypeVar

from psij.job_executor import JobExecutor
from psij.job_executor_config import JobExecutorConfig
from psij.async_job_executor import AsyncJobExecutor
from psij.job import Job, JobStatusCallback
from psij.async_job import AsyncJob, AsyncJobStatusCallback
from psij.job_state import JobState
from psij.job_status import JobStatus
from psij.exceptions import ExecutorException
from psij.base_job import BaseJob
from psij._base_executor import BaseExecutor

T = TypeVar('T')

_EMPTY_CONFIG = JobExecutorConfig()


def set_job_status(executor: BaseExecutor, job: BaseJob, status: JobStatus,
                   loop: Optional[AbstractEventLoop] = None) -> None:
    """Convenience method to update job status.

    This is a method that can be used to call the `_set_job_status` method
    of certain executors that support it for either synchronous or async
    executors.

    Parameters
    ----------
    executor
        An instance of either a :class:`~psij.JobExecutor` or
        :class:`~psij.AsyncJobExecutor`. If the latter, then the job must be
        a :class:`~psij.AsyncJob` and the loop parameter must be specified.
    job
        The job whose status needs to be updated. If the executor is an instance
        of :class:`psij.AsyncJobExecutor`, then the job must be a
        :class:`psij.AsyncJob`.
    status
        The new status.
    loop
        An asyncio event loop to use if invoking an async version of the
        `_set_job_status` method. In general, the loop must match the loop
        from which the executor's `submit` method was invoked.
    """
    if loop is not None:
        assert isinstance(executor, AsyncJobExecutor)
        assert isinstance(job, AsyncJob)
        executor.run_coroutine(executor._set_job_status(job, status), loop)
    else:
        assert isinstance(executor, JobExecutor)
        assert isinstance(job, Job)
        executor._set_job_status(job, status)


class _SyncCallbackWrapper(JobStatusCallback):
    def __init__(self, cb: Union[AsyncJobStatusCallback,
                 Callable[[AsyncJob, JobStatus], Awaitable[None]]],
                 exec: AsyncJobExecutor,
                 loop: AbstractEventLoop) -> None:
        self._cb = cb
        self._exec = exec
        self._loop = loop

    def job_status_changed(self, job: Job, job_status: JobStatus) -> None:
        assert isinstance(job, _SyncJobWrapper)
        asyncio.run_coroutine_threadsafe(self._cb(job._job, job_status),  # type: ignore
                                         loop=self._loop)


class _SyncJobWrapper(Job):
    def __init__(self, async_job: AsyncJob, exec: AsyncJobExecutor,
                 loop: AbstractEventLoop) -> None:
        super().__init__(async_job.spec)
        self._async_job = async_job
        self._id = async_job._id
        self._exec = exec
        self._loop = loop

    def cancel(self) -> None:
        # not called
        pass

    def wait(self, timeout: Optional[timedelta] = None,
             target_states: Optional[Union[JobState, Sequence[JobState]]] = None) \
            -> Optional[JobStatus]:
        # not called directly either because we forward events to the original job
        pass

    @property
    def native_id(self) -> Optional[str]:
        return self._async_job.native_id

    @native_id.setter
    def native_id(self, native_id: str) -> None:
        self._async_job.native_id = native_id

    def set_status(self, status: JobStatus) -> None:
        set_job_status(self._exec, self._async_job, status, self._loop)


class AsyncExecutorWrapper(AsyncJobExecutor):
    """A class that converts a normal executor to an async executor.

    This class can be used to provide an async version of an executor when only
    a synchronous version exists and it is otherwise unfeasible to provide a
    native async executor for the specific backend. This class should seldom
    be used. A better option is to provide a proper subclass of
    :class:`~psij.AsyncJobExecutor`.

    This class does not provide a constructor compatible with the PSI/J
    instantiation mechanism and cannot be registered directly from a descriptor.
    If an instance of this wrapper needs to be registered through a descriptor,
    the preferred method is to subclass this class and register the resulting
    subclass:

        class MyAsyncExecutor(AsyncExecutorWrapper):
            def __init__(self, url: Optional[str] = None,
                 config: Optional[JobExecutorConfig] = None):
                 super().__init__(MySyncJobExecutor(url, config))
    """

    def __init__(self, executor: JobExecutor) -> None:
        """
        Parameters
        ----------
        executor
            The underlying synchronous executor.
        """
        super().__init__(config=_EMPTY_CONFIG)
        self._cb: Optional[AsyncJobStatusCallback] = None
        self._executor = executor
        self._executor.set_job_status_callback(self._job_status_callback)
        self._wrappers: Dict[str, _SyncJobWrapper] = {}

    async def submit(self, job: AsyncJob) -> None:
        """See :meth:`~psij.AsyncJobExecutor.submit`."""
        wrapper = _SyncJobWrapper(job, self, asyncio.get_running_loop())
        self._wrappers[job.id] = wrapper
        await asyncio.to_thread(self._executor.submit, wrapper)
        job.executor = self

    async def cancel(self, job: AsyncJob) -> None:
        """See :meth:`~psij.AsyncJobExecutor.cancel`."""
        try:
            wrapper = self._wrappers[job.id]
        except KeyError:
            raise ExecutorException(f'The job {job.id} is not being executed by this executor.')
        await asyncio.to_thread(self._executor.cancel, wrapper)

    async def list(self) -> List[str]:
        """See :meth:`~psij.AsyncJobExecutor.list`."""
        return await asyncio.to_thread(self._executor.list)

    async def attach(self, job: AsyncJob, native_id: str) -> None:
        """See :meth:`~psij.AsyncJobExecutor.attach`."""
        wrapper = _SyncJobWrapper(job, self, asyncio.get_running_loop())
        self._wrappers[job.id] = wrapper
        await asyncio.to_thread(self._executor.attach, wrapper, native_id)

    def _job_status_callback(self, job: Job, status: JobStatus) -> None:
        if status.final:
            del self._wrappers[job.id]

    async def set_job_status_callback(self, cb: Union[AsyncJobStatusCallback,
                                      Callable[[AsyncJob, JobStatus], Awaitable[None]]]) -> None:
        """See :meth:`~psij.AsyncJobExecutor.set_job_status_callback`."""
        self._executor.set_job_status_callback(_SyncCallbackWrapper(cb, self,
                                                                    asyncio.get_running_loop()))


class _AsyncCallbackWrapper(AsyncJobStatusCallback):
    def __init__(self, cb: Union[JobStatusCallback, Callable[[Job, JobStatus], None]]) -> None:
        self._cb = cb

    async def job_status_changed(self, job: AsyncJob, job_status: JobStatus) -> None:
        assert isinstance(job, _AsyncJobWrapper)
        await asyncio.to_thread(self._cb, job._job, job_status)  # type: ignore


class _AsyncJobWrapper(AsyncJob):
    def __init__(self, job: Job) -> None:
        super().__init__(job.spec)
        self._job = job
        self._id = job._id

    async def cancel(self) -> None:
        # this is never really called
        pass

    async def wait(self, timeout: Optional[timedelta] = None,
                   target_states: Optional[Union[JobState, Sequence[JobState]]] = None) \
            -> Optional[JobStatus]:
        # not called directly either because we forward events to the original job
        pass

    @property
    def native_id(self) -> Optional[str]:
        return self._job.native_id

    @native_id.setter
    def native_id(self, native_id: str) -> None:
        self._job.native_id = native_id

    async def set_status(self, status: JobStatus) -> None:
        await asyncio.to_thread(self._job.set_status, status)


class SyncExecutorWrapper(JobExecutor):
    """A class that converts an async executor to a synchronous executor.

    Given an async executor, this class can be used to provide a synchronous
    view (i.e., an instance of :class:`~.JobExecutor`) of the functionality
    provided by the async executor.

    See :class:`~.AsyncExecutorWrapper` for a class providing the reverse
    functionality.

    It is considerably more acceptable to wrap a natively asynchronous executor
    in a synchronous view than the other way around.

    This wrapper uses an internal event loop.
    """

    _NAME_ = 'SyncExecutorWrapper'
    _VERSION_ = Version('0.0.1')

    _LOOP = None

    @staticmethod
    def _ensure_loop_running() -> AbstractEventLoop:
        if SyncExecutorWrapper._LOOP is not None:
            return SyncExecutorWrapper._LOOP
        SyncExecutorWrapper._LOOP = asyncio.new_event_loop()
        thread = Thread(target=SyncExecutorWrapper._LOOP.run_forever,
                        daemon=True, name='Sync Wrapper Event Loop')
        thread.start()
        return SyncExecutorWrapper._LOOP

    @staticmethod
    def _run_coroutine(c: Coroutine[Any, Any, T]) -> T:
        loop = SyncExecutorWrapper._ensure_loop_running()
        task = asyncio.run_coroutine_threadsafe(c, loop)
        return task.result()

    def __init__(self, executor: AsyncJobExecutor) -> None:
        """
        Parameters
        ----------
        executor
            A :class:`~psij.AsyncJobExecutor` to wrap.
        """
        super().__init__(config=_EMPTY_CONFIG)
        self._cb: Optional[JobStatusCallback] = None
        self._executor = executor
        SyncExecutorWrapper._run_coroutine(
            self._executor.set_job_status_callback(self._job_status_callback))
        self._wrappers: Dict[str, _AsyncJobWrapper] = {}

    def submit(self, job: Job) -> None:
        """See :meth:`~psij.JobExecutor.submit`."""
        wrapper = _AsyncJobWrapper(job)
        self._wrappers[job.id] = wrapper
        print(f'exec: {self._executor}')
        SyncExecutorWrapper._run_coroutine(self._executor.submit(wrapper))
        job.executor = self

    def cancel(self, job: Job) -> None:
        """See :meth:`~psij.JobExecutor.cancel`."""
        try:
            wrapper = self._wrappers[job.id]
        except KeyError:
            raise ExecutorException(f'The job {job.id} is not being executed by this executor.')
        SyncExecutorWrapper._run_coroutine(self._executor.cancel(wrapper))

    def list(self) -> List[str]:
        """See :meth:`~psij.JobExecutor.list`."""
        return SyncExecutorWrapper._run_coroutine(self._executor.list())

    def attach(self, job: Job, native_id: str) -> None:
        """See :meth:`~psij.JobExecutor.attach`."""
        wrapper = _AsyncJobWrapper(job)
        self._wrappers[job.id] = wrapper
        SyncExecutorWrapper._run_coroutine(self._executor.attach(wrapper, native_id))

    async def _job_status_callback(self, job: AsyncJob, status: JobStatus) -> None:
        if status.final:
            del self._wrappers[job.id]

    def set_job_status_callback(self, cb: Union[JobStatusCallback,
                                Callable[[Job, JobStatus], None]]) -> None:
        """See :meth:`~psij.JobExecutor.set_job_status_callback`."""
        SyncExecutorWrapper._run_coroutine(
            self._executor.set_job_status_callback(_AsyncCallbackWrapper(cb)))
