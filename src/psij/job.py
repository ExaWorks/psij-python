import logging
import threading
from abc import ABC, abstractmethod
from datetime import timedelta, datetime
from typing import Optional, Sequence, Union, Callable, Set

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


class Job(BaseJob):
    """
    This class represents a synchronous PSI/J job.

    It encapsulates all of the information needed to run a job as well as the job’s state.
    """

    def __init__(self, spec: Optional[JobSpec] = None) -> None:
        """
        When constructed, a job is in the :attr:`~psij.JobState.NEW` state.

        :param spec: an optional :class:`~psij.JobSpec` that describes the details of the job.
        """
        super().__init__(spec)
        # need indirect ref to avoid a circular reference
        self.executor: Optional['psij.JobExecutor'] = None
        self._cb: Optional[JobStatusCallback] = None
        self._status_cv = threading.Condition()

    @property
    def status(self) -> JobStatus:
        """
        Contains the current status of the job.

        It is guaranteed that the status returned by this property is monotonic in time with respect
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
        # For reference, this is not in BaseJob because defining a setter for an inherited
        # getter doesn't seem to quite work.
        return self._status

    @status.setter
    def status(self, status: JobStatus) -> None:
        """
        Sets this job's status.

        This setter is deprecated. For compatibility with the async conterpart,
        please use the :meth:`set_status` method.
        """
        self.set_status(status)

    def set_status(self, status: JobStatus) -> None:
        """
        Set this job's status.

        For detailed semantics of the status, please see the description of
        the :attr:`status` property.

        Parameters
        ----------
        status
            The new status.
        """
        with self._status_cv:
            crt = self._status.state
            assert crt is not None
            nxt = status.state
            assert nxt is not None
            if crt == nxt:
                return
            gt = crt.is_greater_than(nxt)
            if gt is None or gt:
                # new state is older or not comparable
                return
            prev = JobStateOrder.prev(nxt)
            if prev is not None and prev != crt:
                self.status = JobStatus(prev)
            self._status = status
            self._status_cv.notify_all()
        logger.debug('Job status change %s: %s -> %s', self, self._status.state, status.state)

        if self._cb:
            try:
                self._cb.job_status_changed(self, status)
            except Exception as ex:
                logger.warning('Job status callback for %s threw an exception: %s', self.id, ex)

        if self.executor:
            self.executor._notify_callback(self, status)

    def set_job_status_callback(self,
                                cb: Union['JobStatusCallback',
                                          Callable[['Job', 'psij.JobStatus'], None]]) -> None:
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
        if isinstance(cb, JobStatusCallback):
            self._cb = cb
        else:
            self._cb = FunctionJobStatusCallback(cb)

    def cancel(self) -> None:
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
            self.executor.cancel(self)

    def _all_greater(self, states: Optional[Union[JobState, Sequence[JobState]]]) \
            -> Optional[Set[JobState]]:
        if states is None:
            return None
        if isinstance(states, JobState):
            states = [states]
        ts = set()
        for state1 in states:
            ts.add(state1)
            for state2 in JobState:
                if state2.is_greater_than(state1):
                    ts.add(state2)
        return ts

    def wait(self, timeout: Optional[timedelta] = None,
             target_states: Optional[Union[JobState, Sequence[JobState]]] = None) \
            -> Optional[JobStatus]:
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
            with self._status_cv:
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
                self._status_cv.wait(left_seconds)

    def __hash__(self) -> int:
        """Returns a hash for this job."""
        return hash(self._id)

    def __str__(self) -> str:
        """Returns a string representation of this job."""
        return 'Job[id={}, native_id={}, executor={}, status={}]'.format(self._id, self._native_id,
                                                                         self.executor, self.status)


class JobStatusCallback(ABC):
    """An interface used to listen to job status change events."""

    @abstractmethod
    def job_status_changed(self, job: Job, job_status: JobStatus) -> None:
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


class FunctionJobStatusCallback(JobStatusCallback):
    """A JobStatusCallback that wraps a function."""

    def __init__(self, fn: Callable[[Job, 'psij.JobStatus'], None]):
        """Initializes a `_FunctionJobStatusCallback`."""
        self.fn = fn

    def job_status_changed(self, job: Job, job_status: 'psij.JobStatus') -> None:
        """See :meth:`~.JobStatusCallback.job_status_changed`."""
        self.fn(job, job_status)
