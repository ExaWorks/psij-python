import logging
import threading
from abc import ABC, abstractmethod
from datetime import timedelta, datetime
from typing import Optional, Sequence
from uuid import uuid4

import psij
from psij.exceptions import SubmitException, UnreachableStateException
from psij.job_spec import JobSpec
from psij.job_state import JobState
from psij.job_status import JobStatus

logger = logging.getLogger(__name__)


# timedelta.max can't be added to now since it overflows
# furthermore, timedate.max overflows the timeout to Condition()
LARGE_TIMEOUT = timedelta(days=3650)


def _generate_id() -> str:
    return str(uuid4())


class Job:
    """
    This class represents a PSI/J job.

    It encapsulates all of the information needed to run a job as well as the job’s state.
    """

    def __init__(self, spec: Optional[JobSpec] = None) -> None:
        """
        Constructs a `Job` object.

        The object can optionally be initialized with the given
        :class:`~psij.JobSpec`. After construction, the job will be in the
        :attr:`~psij.JobState.NEW` state.

        :param spec: an optional :class:`~psij.JobSpec`
        """
        self.spec = spec
        """The job specification for this job. A valid job requires a valid specification."""
        self._id = _generate_id()
        self._status = JobStatus(JobState.NEW)
        # need indirect ref to avoid a circular reference
        self._executor = None  # type: Optional['psij.JobExecutor']
        # allow the native ID to be anything and do the string conversion in the getter; there's
        # no point in storing integers as strings.
        self._native_id = None  # type: Optional[object]
        self.status_callback = None  # type: Optional[JobStatusCallback]
        """Setting this property registers a :class:`~psij.JobStatusCallback` with this executor.
        The callback will be invoked whenever a status change occurs for any of the jobs submitted
        to this job executor, whether they were submitted with an individual job status callback or
        not. To remove the callback, set it to `None`."""
        self._status_cv = threading.Condition()
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('New Job: {}'.format(self))

    @property
    def id(self) -> str:
        """
        Returns this job’s ID.

         The ID is assigned automatically by the implementation when this `Job` object is
         constructed. The ID is guaranteed to be unique on the machine on which the `Job` object
         was instantiated. The ID does not have to match the ID of the underlying LRM job, but is
         used to identify `Job` instances as seen by a client application.
        """
        return self._id

    @property
    def native_id(self) -> Optional[str]:
        """
        Returns the native ID of this job.

        The native ID may not be available until after the job is submitted to a
        :class:`~psij.JobExecutor`.
        """
        if self._native_id is None:
            return None
        else:
            return str(self._native_id)

    @property
    def status(self) -> JobStatus:
        """
        Returns the current status of the job.

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

    def cancel(self) -> None:
        """
        Cancels this job.

        The job is canceled by calling :func:`~psij.JobExecutor.cancel` on the job
        executor that was used to submit this job.

        :raises psij.SubmitException: if the job has not yet been submitted.
        """
        if not self._executor:
            raise SubmitException('Cannot cancel job: not bound to an executor.')
        else:
            self._executor.cancel(self)

    def _set_status(self, status: JobStatus,
                    executor: Optional['psij.JobExecutor'] = None) -> None:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Job status change {}: {!s} -> {!s}".format(self, self._status.state,
                                                                     status.state))

        with self._status_cv:
            if executor:
                self._executor = executor
            self._status = status
            self._status_cv.notify_all()

        if self.status_callback:
            self.status_callback.job_status_changed(self, status)

    def wait(self, timeout: Optional[timedelta] = None,
             target_states: Optional[Sequence[JobState]] = None) -> Optional[JobStatus]:
        """
        Waits for the job to reach certain states.

        This method returns either when the job reaches one of the `target_states` or when an
        amount of time indicated by the `timeout` parameter, if specified, passes. Returns the
        :class:`~psij.JobStatus` object that has one of the desired `target_states` or `None` if
        the timeout is reached. If none of the states in `target_states` can be reached (such as,
        for example, because the job has entered the :attr:`~psij.JobState.FAILED` state while
        `target_states` consists of :attr:`~psij.JobState.COMPLETED`), this method throws an
        :class:`~psij.UnreachableStateException`.

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

        while True:
            with self._status_cv:
                status = self.status
                state = status.state
                if target_states:
                    if state in target_states:
                        return status
                    elif state.final:
                        raise UnreachableStateException(status)
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
        return 'Job[id={}, nativeId={}, executor={}, status={}]'.format(self._id, self._native_id,
                                                                        self._executor, self.status)


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
