import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple, Optional, Iterable, Union

from psij import BaseJob, JobStatus, JobState, JobSpec
from psij.exceptions import JobException
from psij.staging import StageIn, StageOut

logger = logging.getLogger(__name__)


class _JobCanceled(BaseException):
    pass


class JobStateMachine(ABC):
    """
    Implements an abstract state machine for running a job.

    This can be used to "execute" the state diagram of a job. The abstract
    methods implement the concrete steps such as staging a file running the
    actual job, etc., while properly handling errors, cancellations, and staging
    flags.
    """

    def __init__(self, job: BaseJob) -> None:
        """
        Parameters
        ----------
        job
            The job to run.
        """
        self.job = job
        self._canceled = False

    @abstractmethod
    def filter_staging(self, spec: JobSpec) \
            -> Tuple[Optional[Iterable[StageIn]], Optional[Iterable[StageOut]],
                     Optional[Iterable[Union[str, Path]]]]:
        """
        Allows filtering of stage ins, stage outs, and cleanups.

        Returns a tuple (stage_ins, stage_outs) each of each is an iterable of
        `StageIn` and `StageOut` directives which should be processed by this
        state machine. Concrete implementations of this method can also change
        staging directives that are in the job specification. This can be useful
        in cases in which the job is forwarded to another executor for actual
        execution.

        Parameters
        ----------
        spec
            The specification of the job whose staging directives should be
            filtered.
        Returns
        -------
            A tuple with the new stage ins, stage outs, and cleanups,
            respectively. Each can be `None` if there are no respective
            directives. For example, (None, None, None) means that there
            are no stage ins, stage outs, or clean up directives.
        """
        pass

    async def run(self) -> None:
        """Implements the main part of the state machine."""
        spec = self.job.spec
        assert spec is not None
        stage_ins, stage_outs, clean_ups = self.filter_staging(spec)
        error: Optional[Exception] = None
        final_state = JobState.NEW
        failure_state = None
        if stage_ins is not None:
            try:
                await self.stage_in(stage_ins)
            except _JobCanceled:
                final_state = JobState.CANCELED
                failure_state = JobState.STAGE_IN
            except Exception as ex:
                error = Exception(f'Stage in failed: {ex}')
                final_state = JobState.FAILED
                failure_state = JobState.STAGE_IN
        if final_state == JobState.NEW:
            try:
                await self.run_job(self.job)
            except _JobCanceled:
                final_state = JobState.CANCELED
                failure_state = JobState.ACTIVE
            except JobException as ex:
                final_state = JobState.FAILED
                error = ex
                failure_state = JobState.ACTIVE
            except Exception as ex:
                error = JobException(f'Failed to run job: {ex}')
                final_state = JobState.FAILED
                failure_state = JobState.ACTIVE
        if stage_outs is not None and not failure_state == JobState.STAGE_IN:
            # if the error occurred during stage in, the job would not have
            # had a chance of producing any useful output, so we skip stage out
            # in that case
            try:
                await self.stage_out(stage_outs, final_state)
            except Exception as ex:
                if error is not None:
                    assert isinstance(error, JobException)
                    error.add_exception(ex)
                else:
                    error = Exception(f'Stage out failed: {ex}')
                final_state = JobState.FAILED
                failure_state = JobState.STAGE_OUT
        if (clean_ups is not None and spec.cleanup_flags.matches(final_state)
                and not failure_state == JobState.STAGE_OUT):
            try:
                await self.clean_up(clean_ups)
            except Exception as ex:
                if error is not None:
                    assert isinstance(error, JobException)
                    error.add_exception(ex)
                else:
                    error = Exception(f'Clean up failed: {ex}')
                final_state = JobState.FAILED
        if final_state == JobState.FAILED:
            assert error is not None
            if isinstance(error, JobException):
                final_status = JobStatus(JobState.FAILED, exit_code=error.exit_code,
                                         message=str(error))
            else:
                final_status = JobStatus(JobState.FAILED, message=str(error))
        else:
            final_status = JobStatus(final_state)
        await self.update_status(final_status)

    def cancel(self) -> None:
        """
        Cancels the job.

        This method sets a flag that signals the `run` method that the job
        should be canceled as soon as feasible.
        """
        self._canceled = True

    @abstractmethod
    async def update_status(self, status: JobStatus) -> None:
        """
        Updates the job status.

        Concrete job runners must implement this method and update the job status.

        Parameters
        ----------
        status
            The new job status.
        """
        pass

    async def stage_in(self, stage_ins: Iterable[StageIn]) -> None:
        """
        Implements the stagein sequence.

        This method is a default stagein implementation. It iterates through
        each stagein directive and calls :meth:`~.stage_in_one`.

        Parameters
        ----------
        stage_ins
            An iterable with the stagein directives.
        """
        await self.update_status(JobStatus(JobState.STAGE_IN))
        for s in stage_ins:
            if self._canceled:
                raise _JobCanceled()
            await self.stage_in_one(s)

    @abstractmethod
    async def stage_in_one(self, s: StageIn) -> None:
        """
        Stages one file in.

        Concrete job runners must implement this method and perform the actual
        staging.

        Parameters
        ----------
        s
            A `StageIn` directive describing the staging operation to be
            performed.
        """
        pass

    async def stage_out(self, stage_outs: Iterable[StageOut], state: JobState) -> None:
        """
        Implements the stageout sequence.

        This method is a default stageout implementation. It iterates through
        each stageout directive and calls :meth:`~.stage_out_one`.

        Parameters
        ----------
        stage_outs
            An iterable with the stageout directives.
        """
        assert stage_outs is not None
        await self.update_status(JobStatus(JobState.STAGE_OUT))
        for s in stage_outs:
            if s.flags.matches(state):
                await self.stage_out_one(s)

    @abstractmethod
    async def stage_out_one(self, s: StageOut) -> None:
        """
        Stages one file out.

        Concrete job runners must implement this method and perform the actual
        staging.

        Parameters
        ----------
        s
            A `StageOut` directive describing the staging operation to be
            performed.
        """
        pass

    @abstractmethod
    async def run_job(self, job: BaseJob) -> None:
        """
        Runs the actual job.

        Concrete job runners must implement this method and perform the actual
        invocation of the job.

        Parameters
        ----------
        job
            The job to run.
        """
        pass

    @abstractmethod
    async def clean_up(self, clean_ups: Iterable[Union[str, Path]]) -> None:
        """
        Implements the cleanup sequence.

        Concrete job runners must implement this method and perform the actual
        cleanup.

        Parameters
        ----------
        clean_ups
            An iterable with the cleanup paths.
        """
        pass
