from enum import Enum
from typing import Optional


_NAME_MAP = {}

class JobState(bytes, Enum):
    """
    An enumeration holding the possible job states.

    The possible states are: `NEW`, `QUEUED`, `ACTIVE`, `COMPLETED`, `FAILED`, and `CANCELED`.
    """

    def __new__(cls, index: int, order: int, name: str, final: bool) -> 'JobState':  # noqa: D102
        # This is used internally to allow enum initialization with multiple parameters
        obj: 'JobState' = bytes.__new__(cls)
        obj._value_ = index
        obj._order = order
        obj._name = name
        obj._final = final
        _NAME_MAP[name] = obj
        return obj

    def __init__(self, *args: object) -> None:  # noqa: D107
        # this is only here to declare the types of the properties
        self._order: int = self._order
        self._name: str = self._name
        self._final: bool = self._final

    NEW = (0, 0, 'NEW', False)
    """
    This is the state of a job immediately after the :class:`~psij.Job` object is created and
    before being submitted to a :class:`~psij.JobExecutor`.
    """
    QUEUED = (1, 1, 'QUEUED', False)
    """
    This is the state of the job after being accepted by a backend for execution, but before the
    execution of the job begins.
    """
    STAGE_IN = (2, 2, 'STAGE_IN', False)
    """
    This state indicates that the job is staging files in, in preparation for execution.
    """
    ACTIVE = (3, 3, 'ACTIVE', False)
    """This state represents an actively running job."""
    STAGE_OUT = (4, 4, 'STAGE_OUT', False)
    """
    This state indicates that the executable has finished running and that files are being staged
    out.
    """
    CLEANUP = (5, 5, 'CLEANUP', False)
    """
    This state indicates that cleanup is actively being done for this job.
    """
    COMPLETED = (6, 6, 'COMPLETED', True)
    """
    This state represents a job that has completed *successfully* (i.e., with a zero exit code).
    In other words, a job with the executable set to `/bin/false` cannot enter this state.
    """
    FAILED = (7, 6, 'FAILED', True)
    """
    Represents a job that has either completed unsuccessfully (with a non-zero exit code) or a job
    whose handling and/or execution by the backend has failed in some way.
    """
    CANCELED = (8, 6, 'CANCELED', True)
    """Represents a job that was canceled by a call to :func:`~psij.Job.cancel()`."""

    def is_greater_than(self, other: 'JobState') -> Optional[bool]:
        """
        Defines a (strict) partial ordering on the states.

        Not all states are comparable. State transitions cannot violate this ordering.

        :param other: the other `JobState` to compare to
        :return: if this state is comparable with `other`, this method returns `True` or
            `False` depending on the relative order between this state and `other`. That is,
            `True` is returned if and only if this state can come after `other`. If this state
            is not comparable with `other`, this method returns `None`.
        """
        if self._order == other._order:
            if self._value_ == other._value_:
                # same state, so not strictly greater
                return False
            else:
                # not comparable
                return None
        else:
            return self._order > other._order

    @property
    def final(self) -> bool:
        """
        Returns `True` if this state final.

        A state is final when no other state transition can occur after that state has been reached.

        :return: `True` if this is a final state and `False` otherwise
        """
        return self._final

    def __str__(self) -> str:
        """Returns a string representation of this job state."""
        return self.__repr__()

    def __repr__(self) -> str:
        """Returns a string representation of this job state."""
        return self._name

    def __eq__(self, other: object) -> bool:
        """Returns true if `other` represents the same state as this state."""
        if isinstance(other, JobState):
            return bool(self._value_ == other._value_)
        else:
            return False

    def __ne__(self, other: object) -> bool:
        """Returns false only if `other` represents the same state as this state."""
        if isinstance(other, JobState):
            return bool(self._value_ != other._value_)
        else:
            return True

    def __bool__(self) -> bool:
        """All states are consider true-ish."""
        return True

    def __hash__(self) -> int:
        """Returns a hash for this object."""
        return self._value_  # type: ignore

    @staticmethod
    def from_name(name: str) -> 'JobState':
        return _NAME_MAP[name]


_PREV_STATE = {
    JobState.NEW: None,
    JobState.QUEUED: JobState.NEW,
    JobState.STAGE_IN: JobState.QUEUED,
    JobState.ACTIVE: JobState.STAGE_IN,
    JobState.STAGE_OUT: JobState.ACTIVE,
    JobState.CLEANUP: JobState.STAGE_OUT,
    JobState.COMPLETED: JobState.CLEANUP,
    JobState.FAILED: None,
    JobState.CANCELED: None
}

class JobStateOrder:
    """A class that can be used to reconstruct missing states."""

    @staticmethod
    def prev(state: JobState) -> Optional[JobState]:
        """Returns the state previous to the given state.

        The "previous" state is a state that must have occurred immediately prior to this state
        given the state transition diagram if such a state is unique. Not all states have a
        previous state. For example, the FAILED state does not have a previous state, since it can
        be reached from multiple states.
        """
        return _PREV_STATE[state]
