import time as t
from typing import Optional, Dict

from psij.job_state import JobState


class JobStatus(object):
    """A class containing details about job transitions to new states."""

    def __init__(self, state: JobState, time: Optional[float] = None,
                 message: Optional[str] = None, exit_code: Optional[int] = None,
                 metadata: Optional[Dict[str, object]] = None) -> None:
        """
        Constructs a `JobStatus` object.

        :param state: The :class:`~psij.JobState` of this status.
        :param time: The time, as would be returned by :func:`time.time()` that the transition to
            the new state occurred. If `None`, the current time will be used.
        :param message: An optional message associated with the transition.
        :param exit_code: An optional exit code for the job, if the job has completed.
        :param metadata: Optional metadata provided by the :class:`~psij.JobExecutor`.
        """
        self.state = state
        if time is not None:
            self.time = time
        else:
            self.time = t.time()
        self.message = message
        self.exit_code = exit_code
        self.metadata = metadata

    @property
    def final(self) -> bool:
        """
        Returns the `final` property of the underlying state.

        :return: `True` if the state is final and `False` otherwise.
        """
        return self.state.final

    def __str__(self) -> str:
        """Returns a string representation of this `JobStatus` instance."""
        s = 'JobStatus[{!s}, time={}'.format(self.state, self.time)
        if self.message is not None:
            s = s + ', message={}'.format(self.message)
        if self.exit_code is not None:
            s = s + ', exit_code={}'.format(self.exit_code)
        if self.metadata is not None:
            s = s + ', meta={}'.format(self.metadata)
        return s + ']'
