from distutils.version import StrictVersion
from pathlib import Path
from typing import Optional, Collection, List, Dict, TextIO

from psij import Job, JobStatus, JobState, SubmitException
from psij.executors.batch.batch_scheduler_executor import BatchSchedulerExecutor, \
    BatchSchedulerExecutorConfig, check_status_exit_code
from psij.executors.batch.script_generator import TemplatedScriptGenerator

import json
import time

_QSTAT_COMMAND = 'qstat'

_STATE_MAP = {
        'Q': JobState.QUEUED,
        'R': JobState.ACTIVE,
        'F': JobState.COMPLETED, # this happens for failed jobs too, so need to rely on .ec handling for failure detection
        'E': JobState.ACTIVE # exiting after running - TODO: unclear to me if this is finished enough to regard as completed, or if it shoudl still be active? parsl treats it as completed.
    }



class PBSProExecutorConfig(BatchSchedulerExecutorConfig):
    """A configuration class for the PBS executor.
    This doesn't have any fields in addition to BatchSchedulerExecutorCOnfig,
    but it is expected that some will appear during further development."""

    pass


class PBSProJobExecutor(BatchSchedulerExecutor):
    """A :proc:`~psij.JobExecutor` for PBS Pro."""

    # TODO: find a comprehensive list of possible states. at least look in parsls state map.
    def __init__(self, url: Optional[str] = None, config: Optional[PBSProExecutorConfig] = None):
        """Initializes a :proc:`~PBSProJobExecutor`."""
        if not config:
            config = PBSProExecutorConfig()
        super().__init__(url=url, config=config)
        self.generator = TemplatedScriptGenerator(config, Path(__file__).parent / 'pbspro'
                                                  / 'pbspro.mustache')

    def generate_submit_script(self, job: Job, context: Dict[str, object],
                               submit_file: TextIO) -> None:
        """See :proc:`~BatchSchedulerExecutor.generate_submit_script`."""
        self.generator.generate_submit_script(job, context, submit_file)

    def get_submit_command(self, job: Job, submit_file_path: Path) -> List[str]:
        """See :proc:`~BatchSchedulerExecutor.get_submit_command`."""
        return ['qsub', str(submit_file_path.absolute())]

    def get_cancel_command(self, native_id: str) -> List[str]:
        """See :proc:`~BatchSchedulerExecutor.get_cancel_command`."""
        # the slurm cancel command had a -Q parameter
        # which does not report an error if the job is already
        # completed.
        # TODO: whats the pbs equivalent of that?
        # there is -x which also removes job history (so would need to 
        # check that this doesn't cause implicit COMPLETED states when
        # maybe it should be cancelled states?)
        return ['qdel', native_id]

    def process_cancel_command_output(self, exit_code: int, out: str) -> None:
        """See :proc:`~BatchSchedulerExecutor.process_cancel_command_output`."""
        raise SubmitException('Failed job cancel job: %s' % out)


    def cancel(self, job):
        super().cancel(job)
        job_status = JobStatus(JobState.CANCELED, time=time.time())
        self._update_job_status(job, job_status)


    def get_status_command(self, native_ids: Collection[str]) -> List[str]:
        """See :proc:`~BatchSchedulerExecutor.get_status_command`."""
        ids = ','.join(native_ids)

        # -x will include finished jobs
        # -f -F json will give json status output that is more mechanically
        # parseable that the default human readable output. Most importantly,
        # native job IDs will be full length and so match up with the IDs
        # returned by qsub. (123.a vs 123.a.domain.foo)
        return [_QSTAT_COMMAND,  '-f', '-F', 'json', '-x'] + list(native_ids)

    def parse_status_output(self, exit_code: int, out: str) -> Dict[str, JobStatus]:
        """See :proc:`~BatchSchedulerExecutor.parse_status_output`."""
        check_status_exit_code(_QSTAT_COMMAND, exit_code, out)
        r = {}

        report = json.loads(out)
        jobs = report['Jobs']
        for native_id in jobs:
            job_report = jobs[native_id]
            native_state = job_report["job_state"]
            state = self._get_state(native_state)

            # elaborate on the native state if its a completion state, trying to
            # find further evidence of success or failure.
            # for example in my current failure mode on ALCF, I'm seeing
            #             "Exit_status":-2,
            # so whats the "success value" for that? I'll assume 0.

            if state == JobState.COMPLETED:
                if 'Exit_status' in job_report and job_report['Exit_status'] != 0:
                    state = JobState.FAILED

            # right now I haven't implemented msg - maybe there's a field in a richer output form.
            # msg = self._get_message(cols[2]) if state == JobState.FAILED else None
            #  - in JSON form there probably is something like "comment" ?
            # is it ok to use msg the whole time?
            msg = job_report["comment"]
            r[native_id] = JobStatus(state, message=msg)

        return r

    def _get_state(self, state: str) -> JobState:
        assert state in _STATE_MAP, f"PBS state {state} is not known to PSI/J"
        return _STATE_MAP[state]

    # not used
    # def _get_message(self, reason: str) -> str:
    #    assert reason in PBSJobExecutor._REASONS_MAP
    #    return PBSJobExecutor._REASONS_MAP[reason]

    def job_id_from_submit_output(self, out: str) -> str:
        """See :proc:`~BatchSchedulerExecutor.job_id_from_submit_output`."""
        return out.strip().split()[-1]
