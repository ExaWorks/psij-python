from enum import Enum
from typing import Optional


class JobState(bytes, Enum):
    """
    An enumeration holding the possible job states.

    The possible states are: `NEW`, `QUEUED`, `ACTIVE`, `COMPLETED`, `FAILED`, and `CANCELED`.
    """

    def __new__(cls, index: int, order: int, name: str, final: bool) -> 'JobState':
        # noqa: D102
        # This is used internally to allow enum initialization with multiple parameters
        obj = bytes.__new__(cls)  # type: 'JobState'
        obj._value_ = index
        obj._order = order
        obj._name = name
        obj._final = final
        return obj

    def __init__(self, *args: object) -> None:
        # noqa: D107
        # this is only here to declare the types of the properties
        self._order = self._order  # type: int
        self._name = self._name  # type: str
        self._final = self._final  # type: bool

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
    ACTIVE = (2, 2, 'ACTIVE', False)
    """This state represents an actively running job."""
    COMPLETED = (3, 3, 'COMPLETED', True)
    """
    This state represents a job that has completed *successfully* (i.e., with a zero exit code).
    In other words, a job with the executable set to `/bin/false` cannot enter this state.
    """
    FAILED = (4, 3, 'FAILED', True)
    """
    Represents a job that has either completed unsuccessfully (with a non-zero exit code) or a job
    whose handling and/or execution by the backend has failed in some way.
    """
    CANCELED = (5, 3, 'CANCELED', True)
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
