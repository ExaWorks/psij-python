import logging
from abc import abstractmethod
from typing import Optional, Sequence, Union, Set
from uuid import uuid4

import psij
from psij.job_spec import JobSpec
from psij.job_state import JobState
from psij.job_status import JobStatus


logger = logging.getLogger(__name__)


def _generate_id() -> str:
    return str(uuid4())


class BaseJob(object):
    """This class is a superclass of all PSI/J job classes.

    It contains all properties and functionality that is common to both synchronous and asyncio
    based jobs.
    """

    def __init__(self, spec: Optional[JobSpec] = None) -> None:
        """
        When constructed, a job is in the :attr:`~psij.JobState.NEW` state.

        :param spec: an optional :class:`~psij.JobSpec` that describes the details of the job.
        """
        self.spec = spec
        """The job specification of this job."""
        self._id = _generate_id()
        self._status = JobStatus(JobState.NEW)
        # allow the native ID to be anything and do the string conversion in the getter; there's
        # no point in storing integers as strings.
        self._native_id: Optional[object] = None
        self.executor: Optional['psij._base_executor.BaseExecutor'] = None
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('New Job: {}'.format(self))

    @property
    def id(self) -> str:
        """
        A read-only property containing the PSI/J job ID.

        The ID is assigned automatically by the implementation when this `Job` object is
        constructed. The ID is guaranteed to be unique on the machine on which the `Job` object
        was instantiated. The ID does not have to match the ID of the underlying LRM job, but is
        used to identify `Job` instances as seen by a client application.
        """
        return self._id

    @property
    def native_id(self) -> Optional[str]:
        """A property containing the native ID of the job.

        The native ID is the ID assigned to the job by the underlying implementation. The native ID
        may not be available until after the job is submitted to a :class:`~psij.JobExecutor`, in
        which case the value of this property is ``None``.
        """
        if self._native_id is None:
            return None
        else:
            return str(self._native_id)

    @native_id.setter
    def native_id(self, native_id: str) -> None:
        """Sets this job's native ID.

        If this job already has a native ID, a ValueError is raised.

        :param native_id: The native ID to set.
        """
        if self._native_id is None:
            self._native_id = native_id
        else:
            raise ValueError('This job already has a native ID.')

    @property
    @abstractmethod
    def status(self) -> JobStatus:
        """Contains the current status of the job."""
        pass

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

    def __hash__(self) -> int:
        """Returns a hash for this job."""
        return hash(self._id)

    def __str__(self) -> str:
        """Returns a string representation of this job."""
        return 'Job[id={}, native_id={}, status={}]'.format(self._id, self._native_id,
                                                            self.status)
