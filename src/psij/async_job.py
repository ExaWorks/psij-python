import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from datetime import timedelta, datetime
from typing import Optional, Sequence, Union, Callable, Awaitable

import psij
from psij.base_job import BaseJob
from psij.exceptions import SubmitException
from psij.job_spec import JobSpec
from psij.job_state import JobState, JobStateOrder
from psij.job_status import JobStatus


logger = logging.getLogger(__name__)


# timedelta.max can't be added to now since it overflows
# furthermore, timedate.max overflows the timeout to Condition()
LARGE_TIMEOUT = timedelta(days=3650)


class AsyncJob(BaseJob):
    """
    This class represents an async job PSI/J job.

    Instances of `AsyncJob` are used with async executors.
    """

    def __init__(self, spec: Optional[JobSpec] = None) -> None:
        """
        When constructed, a job is in the :attr:`~psij.JobState.NEW` state.

        :param spec: an optional :class:`~psij.JobSpec` that describes the details of the job.
        """
        super().__init__(spec)
        # need indirect ref to avoid a circular reference
        self.executor: Optional['psij.AsyncJobExecutor'] = None
        self._cb: Optional[AsyncJobStatusCallback] = None
        self._status_cv = asyncio.Condition()

    @property
    def status(self) -> JobStatus:
        """
        Contains the current status of the job.

        It is guaranteed that the status returned by this method is monotonic in time with respect
        to the partial ordering of :class:`~psij.JobStatus` types. That is, if
        `job_status_1.state` and `job_status_2.state` are comparable and
        `job_status_1.state < job_status_2.state`, then it is impossible for `job_status_2` to be
        returned by a call placed prior to a call that returns `job_status_1` if both calls are
        placed from the same thread or if a proper memory barrier is placed between the calls.
        Furthermore the job is guaranteed to go through all intermediate states in the
        `state model <https://exaworks.org/job-api-spec/specification#state-model>`_ before
        reaching a particular state.

        :return: the current state of this job
        """
        return self._status

    async def set_status(self, status: JobStatus) -> None:
        """
        Set this job's status.

        For detailed semantics of the status, please see the description of
        the :attr:`status` property.

        Parameters
        ----------
        status
            The new status.
        """
        async with self._status_cv:
            crt = self._status.state
            assert crt is not None
            nxt = status.state
            assert nxt is not None
            if crt == nxt or crt.is_greater_than(nxt):
                return
            prev = JobStateOrder.prev(nxt)
            missing = prev is not None and prev != crt
            if not missing:
                # we can do things here without releasing and re-acquiring the lock
                logger.debug('Job status change %s: %s -> %s', self, self._status.state,
                             status.state)
                self._status = status
                self._status_cv.notify_all()
        if missing:
            assert prev is not None
            await self.set_status(JobStatus(prev))
            logger.debug('Job status change %s: %s -> %s', self, self._status.state, status.state)
            async with self._status_cv:
                self._status = status
                self._status_cv.notify_all()

        if self._cb:
            try:
                await self._cb.job_status_changed(self, status)
            except Exception as ex:
                logger.warning('Job status callback for %s threw an exception: %s', self.id, ex)

        if self.executor:
            await self.executor._notify_callback(self, status)

    def set_job_status_callback(self, cb: Union['AsyncJobStatusCallback',
                                Callable[['AsyncJob', 'psij.JobStatus'], Awaitable[None]]]) -> None:
        """
        Registers a status callback with this job.

        The callback can either be a subclass of :class:`~psij.job.JobStatusCallback` or a
        procedure accepting two arguments: a :class:`~psij.Job` and a :class:`~psij.JobStatus`.

        The callback is invoked whenever a status change occurs for this job, independent of
        any callback registered on the job's :class:`~psij.JobExecutor`.  The callback can be
        removed by setting this property to ``None``.

        :param cb: An instance of :class:`~psij.job.JobStatusCallback` or a callable with two
            parameters, ``job`` of type :class:`~psij.Job`, ``job_status`` of type
            :class:`~psij.JobStatus`, and returning nothing.
        """
        if isinstance(cb, AsyncJobStatusCallback):
            self._cb = cb
        else:
            self._cb = AsyncFunctionJobStatusCallback(cb)

    async def cancel(self) -> None:
        """
        Cancels this job.

        The job is canceled by calling :func:`~psij.JobExecutor.cancel` on the job
        executor that was used to submit this job.

        :raises SubmitException: if the job has not yet been submitted.
        """
        if self.status.final:
            return
        if not self.executor:
            raise SubmitException('Cannot cancel job: not bound to an executor.')
        else:
            await self.executor.cancel(self)

    async def wait(self, timeout: Optional[timedelta] = None,
                   target_states: Optional[Union[JobState, Sequence[JobState]]] = None) -> \
            Optional[JobStatus]:
        """
        Waits for the job to reach certain states.

        This method returns either when the job reaches one of the `target_states`, a state
        following one of the `target_states`, a final state, or when an amount of time indicated by
        the `timeout` parameter, if specified, passes. Returns the :class:`~psij.JobStatus` object
        that has one of the desired states or `None` if the timeout is reached. For example,
        `wait(target_states = [JobState.QUEUED]` waits until the job is in any of the `QUEUED`,
        `ACTIVE`, `COMPLETED`, `FAILED`, or `CANCELED` states.

        :param timeout: An optional timeout after which this method returns even if none of the
            `target_states` was reached. If not specified, wait indefinitely.
        :param target_states: A set of states to wait for. If not specified, wait for any
            of the :attr:`~psij.JobState.final` states.
        :return: returns the :class:`~psij.JobStatus` object that caused the caused this call to
            complete or `None` if the timeout is specified and reached.
        """
        start = datetime.now()
        if not timeout:
            timeout = LARGE_TIMEOUT
        end = start + timeout

        ts = self._all_greater(target_states)

        while True:
            async with self._status_cv:
                status = self._status
                state = status.state
                assert state is not None
                if ts:
                    if state.final or state in ts:
                        return status
                    else:
                        pass  # wait
                else:
                    if state.final:
                        return status
                    else:
                        pass  # wait

                left = end - datetime.now()
                left_seconds = left.total_seconds()
                if left_seconds <= 0:
                    return None
                try:
                    async with asyncio.timeout(left_seconds):
                        await self._status_cv.wait()
                except TimeoutError:
                    pass


class AsyncJobStatusCallback(ABC):
    """An interface used to listen to job status change events."""

    @abstractmethod
    async def job_status_changed(self, job: AsyncJob, job_status: JobStatus) -> None:
        """
        This method is invoked when a status change occurs on a job.

        Client code interested in receiving status notifications must implement this method. It is
        entirely possible that :attr:`psij.Job.status` when referenced from the body of this
        method would return something different from the `status` passed to this callback. This is
        because the status of the job can be updated during the execution of the body of this
        method and, in particular, before the potential dereference to :attr:`psij.Job.status` is
        made.

        Client code implementing this method must return quickly and cannot be used for lengthy
        processing. Furthermore, client code implementing this method should not throw exceptions.

        :param job: The job whose status has changed.
        :param job_status: The new status of the job.
        """
        pass


class AsyncFunctionJobStatusCallback(AsyncJobStatusCallback):
    """A JobStatusCallback that wraps a function."""

    def __init__(self, fn: Callable[[AsyncJob, 'psij.JobStatus'], Awaitable[None]]):
        """Initializes a `_FunctionJobStatusCallback`."""
        self.fn = fn

    async def job_status_changed(self, job: AsyncJob, job_status: 'psij.JobStatus') -> None:
        """See :,eth:`~.AsyncJobStatusCallback.job_status_changed`."""
        await self.fn(job, job_status)
