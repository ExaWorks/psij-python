"""Defines a JobExecutor for the Cobalt resource manager."""

from pathlib import Path
from typing import Optional, Collection, List, Dict, TextIO
import re
import os
import stat

from psij import Job, JobStatus, JobState, SubmitException
from psij.executors.batch.batch_scheduler_executor import (
    BatchSchedulerExecutor,
    BatchSchedulerExecutorConfig,
    UNKNOWN_ERROR,
    check_status_exit_code,
)
from psij.executors.batch.script_generator import TemplatedScriptGenerator


_QSTAT_STATE_REGEX = re.compile(r"(State\s*:\s*)(\w+)", re.IGNORECASE)
_QSTAT_JOBID_REGEX = re.compile(r"(Jobid\s*:\s*)([0-9]{4,})", re.IGNORECASE)
_QSUB_REGEX = re.compile(r"\b[0-9]{4,}\b", re.IGNORECASE)
_QSTAT_COMMAND = "qstat"


class CobaltExecutorConfig(BatchSchedulerExecutorConfig):
    """A configuration class for the Cobalt executor."""


class CobaltJobExecutor(BatchSchedulerExecutor):
    """A :proc:`~psij.JobExecutor` for the Cobalt Workload Manager."""

    # see https://Cobalt.schedmd.com/squeue.html
    _STATE_MAP = {
        "starting": JobState.ACTIVE,
        "queued": JobState.QUEUED,
        "running": JobState.ACTIVE,
        "exiting": JobState.ACTIVE,
        "killing": JobState.FAILED,
    }

    def __init__(
        self, url: Optional[str] = None, config: Optional[CobaltExecutorConfig] = None
    ):
        """Initializes a :proc:`~CobaltJobExecutor`."""
        if not config:
            config = CobaltExecutorConfig()
        super().__init__(config=config)
        self.generator = TemplatedScriptGenerator(
            config, Path(__file__).parent / "cobalt" / "cobalt.mustache"
        )

    def generate_submit_script(
        self, job: Job, context: Dict[str, object], submit_file: TextIO
    ) -> None:
        """See :proc:`~BatchSchedulerExecutor.generate_submit_script`."""
        self.generator.generate_submit_script(job, context, submit_file)

    def get_submit_command(self, job: Job, submit_file_path: Path) -> List[str]:
        """See :proc:`~BatchSchedulerExecutor.get_submit_command`."""
        str_path = str(submit_file_path.absolute())
        os.chmod(str_path, os.stat(str_path).st_mode | stat.S_IEXEC)
        return ["qsub", str_path]

    def get_cancel_command(self, native_id: str) -> List[str]:
        """See :proc:`~BatchSchedulerExecutor.get_cancel_command`."""
        return ["qdel", native_id]

    def process_cancel_command_output(self, exit_code: int, out: str) -> None:
        """See :proc:`~BatchSchedulerExecutor.process_cancel_command_output`.

        This should be unnecessary because `qdel` only seems to fail on
        non-integer job IDs.
        """
        raise SubmitException("Failed job cancel job: %s" % out)

    def get_status_command(self, native_ids: Collection[str]) -> List[str]:
        """See :proc:`~BatchSchedulerExecutor.get_status_command`."""
        return [_QSTAT_COMMAND, "-l", "--header=Jobid:State", *native_ids]

    def parse_status_output(self, exit_code: int, out: str) -> Dict[str, JobStatus]:
        """See :proc:`~BatchSchedulerExecutor.parse_status_output`."""
        # if none of the job ID passed to Cobalt are recognized, qstat returns 1,
        # but we shouldn't treat that as an error
        if exit_code != 0 and out == UNKNOWN_ERROR:
            return {}
        check_status_exit_code(_QSTAT_COMMAND, exit_code, out)
        job_statuses = {}
        index = 0
        lines = out.split("\n")
        while index < len(lines) - 1:
            jobid_match = _QSTAT_JOBID_REGEX.search(lines[index])
            if jobid_match is not None:
                state_match = _QSTAT_STATE_REGEX.search(lines[index + 1])
                if state_match is not None:
                    job_statuses[jobid_match.group(2)] = JobStatus(
                        self._STATE_MAP[state_match.group(2)]
                    )
                    index += 2
                else:
                    index += 1
            else:
                index += 1
        return job_statuses

    def job_id_from_submit_output(self, out: str) -> str:
        """See :proc:`~BatchSchedulerExecutor.job_id_from_submit_output`."""
        match = _QSUB_REGEX.search(out)
        if match is None:
            raise SubmitException(out)
        return match.group(0)
