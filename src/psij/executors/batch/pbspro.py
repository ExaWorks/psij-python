from pathlib import Path
from typing import Optional, Collection, List, Dict, TextIO

from psij import Job, JobStatus, JobState, SubmitException
from psij.executors.batch.batch_scheduler_executor import BatchSchedulerExecutor, \
    BatchSchedulerExecutorConfig, check_status_exit_code
from psij.executors.batch.script_generator import TemplatedScriptGenerator

import json

_QSTAT_COMMAND = 'qstat'

# This table maps PBS Pro state codes to the corresponding PSI/J
# JobState.
# See https://www.altair.com/pdfs/pbsworks/PBSReferenceGuide2021.1.pdf
# page 361, section 8.1 "Job States"
_STATE_MAP = {
    'Q': JobState.QUEUED,
    'R': JobState.ACTIVE,

    'F': JobState.COMPLETED,  # This happens for failed jobs too, so
                              # need to rely on richer JSON status codes
                              # and .ec file handling for failure detection

    'E': JobState.ACTIVE      # This state could ambiguously be either the
                              # very end of being ACTIVE or the very
                              # beginning of being COMPLETED. This mapping
                              # treats it as ACTIVE because not all final
                              # job information has appeared in JSON yet.
}


class PBSProExecutorConfig(BatchSchedulerExecutorConfig):
    """A configuration class for the PBS executor.
    This doesn't have any fields in addition to BatchSchedulerExecutorCOnfig,
    but it is expected that some will appear during further development."""

    pass


class PBSProJobExecutor(BatchSchedulerExecutor):
    """A :class:`~psij.JobExecutor` for PBS Pro."""

    # TODO: find a comprehensive list of possible states. at least look in parsls state map.
    def __init__(self, url: Optional[str] = None, config: Optional[PBSProExecutorConfig] = None):
        """Initializes a :class:`~PBSProJobExecutor`."""
        if not config:
            config = PBSProExecutorConfig()
        super().__init__(url=url, config=config)
        self.generator = TemplatedScriptGenerator(config, Path(__file__).parent / 'pbspro'
                                                  / 'pbspro.mustache')

    # Submit methods

    def generate_submit_script(self, job: Job, context: Dict[str, object],
                               submit_file: TextIO) -> None:
        """See :meth:`~BatchSchedulerExecutor.generate_submit_script`."""
        self.generator.generate_submit_script(job, context, submit_file)

    def get_submit_command(self, job: Job, submit_file_path: Path) -> List[str]:
        """See :meth:`~BatchSchedulerExecutor.get_submit_command`."""
        return ['qsub', str(submit_file_path.absolute())]

    def job_id_from_submit_output(self, out: str) -> str:
        """See :meth:`~BatchSchedulerExecutor.job_id_from_submit_output`."""
        return out.strip().split()[-1]

    # Cancel methods

    def get_cancel_command(self, native_id: str) -> List[str]:
        """See :meth:`~BatchSchedulerExecutor.get_cancel_command`."""
        # the slurm cancel command had a -Q parameter
        # which does not report an error if the job is already
        # completed.
        # TODO: whats the pbs equivalent of that?
        # there is -x which also removes job history (so would need to
        # check that this doesn't cause implicit COMPLETED states when
        # maybe it should be cancelled states?)
        return ['qdel', native_id]

    def process_cancel_command_output(self, exit_code: int, out: str) -> None:
        """See :meth:`~BatchSchedulerExecutor.process_cancel_command_output`."""
        raise SubmitException('Failed job cancel job: %s' % out)

    # Status methods

    def get_status_command(self, native_ids: Collection[str]) -> List[str]:
        """See :meth:`~BatchSchedulerExecutor.get_status_command`."""

        # -x will include finished jobs
        # -f -F json will give json status output that is more mechanically
        # parseable that the default human readable output. Most importantly,
        # native job IDs will be full length and so match up with the IDs
        # returned by qsub. (123.a vs 123.a.domain.foo)
        return [_QSTAT_COMMAND, '-f', '-F', 'json', '-x'] + list(native_ids)

    def parse_status_output(self, exit_code: int, out: str) -> Dict[str, JobStatus]:
        """See :meth:`~BatchSchedulerExecutor.parse_status_output`."""
        check_status_exit_code(_QSTAT_COMMAND, exit_code, out)
        r = {}

        report = json.loads(out)
        jobs = report['Jobs']
        for native_id in jobs:
            job_report = jobs[native_id]
            native_state = job_report["job_state"]
            state = self._get_state(native_state)

            if state == JobState.COMPLETED:
                if 'Exit_status' in job_report and job_report['Exit_status'] == 265:
                    state = JobState.CANCELED
                elif 'Exit_status' in job_report and job_report['Exit_status'] != 0:
                    state = JobState.FAILED

            msg = job_report["comment"]
            r[native_id] = JobStatus(state, message=msg)

        return r

    def _get_state(self, state: str) -> JobState:
        assert state in _STATE_MAP, f"PBS state {state} is not known to PSI/J"
        return _STATE_MAP[state]
