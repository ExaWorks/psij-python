"""Defines the LsfJobExecutor class and its config class."""

from distutils.version import StrictVersion
from pathlib import Path
import re
import json
from typing import Optional, Collection, List, Dict, TextIO

from psij import Job, JobStatus, JobState, SubmitException
from psij.executors.batch.batch_scheduler_executor import (
    BatchSchedulerExecutor,
    BatchSchedulerExecutorConfig,
)
from psij.executors.batch.script_generator import TemplatedScriptGenerator


_BKILL_FAILURE_REGEX = re.compile(
    r"(no matching job)|(already finished)", re.IGNORECASE
)
_BSUB_REGEX = re.compile(r"Job <[0-9]+>", re.IGNORECASE)


class LsfExecutorConfig(BatchSchedulerExecutorConfig):
    """A configuration class for the LSF executor."""


class LsfJobExecutor(BatchSchedulerExecutor):
    """A :proc:`~psij.JobExecutor` for the LSF Workload Manager."""

    _NAME_ = "lsf"
    _VERSION_ = StrictVersion("0.0.1")

    # see https://www.ibm.com/docs/en/spectrum-lsf/10.1.0?topic=bjobs-description
    _STATE_MAP = {
        "PEND": JobState.QUEUED,  # normal queued state
        "PROV": JobState.QUEUED,  # The job has been dispatched...
        "PSUSP": JobState.QUEUED,  # The job has been suspended... while pending.
        "RUN": JobState.ACTIVE,  # The job is currently running.
        "USUSP": JobState.ACTIVE,  # The job has been suspended... while running.
        "SSUSP": JobState.ACTIVE,  # The job has been suspended by LSF
        "DONE": JobState.COMPLETED,  # normal 0 exit
        "EXIT": JobState.FAILED,  # nonzero exit
        "UNKWN": JobState.ACTIVE,  # mbatchd has lost contact with the job host...
        "WAIT": JobState.QUEUED,  # For... members of a chunk job waiting to run.
        "ZOMBI": JobState.ACTIVE,  # something unusual, but probably active
    }

    def __init__(self, url: Optional[str], config: Optional[LsfExecutorConfig] = None):
        """Initializes a :proc:`~LsfJobExecutor`."""
        if not config:
            config = LsfExecutorConfig()
        super().__init__(config=config)
        self.generator = TemplatedScriptGenerator(
            config, Path(__file__).parent / "batch" / "lsf" / "lsf.mustache"
        )

    def generate_submit_script(
        self, job: Job, context: Dict[str, object], submit_file: TextIO
    ) -> None:
        """See :proc:`~BatchSchedulerExecutor.generate_submit_script`."""
        assert(job.spec is not None)
        context["job_duration"] = int(job.spec.attributes.duration.total_seconds() // 60)
        self.generator.generate_submit_script(job, context, submit_file)

    def get_submit_command(self, job: Job, submit_file_path: Path) -> List[str]:
        """See :proc:`~BatchSchedulerExecutor.get_submit_command`."""
        return ["bsub", str(submit_file_path.absolute())]

    def get_cancel_command(self, native_id: str) -> List[str]:
        """See :proc:`~BatchSchedulerExecutor.get_cancel_command`.

        ``bkill`` will exit with an error set if the job does not exist
        or has already finished.
        """
        return ["bkill", native_id]

    def process_cancel_command_output(self, exit_code: int, out: str) -> None:
        """See :proc:`~BatchSchedulerExecutor.process_cancel_command_output`.

        Check if the error was raised only because a job
        """
        if _BKILL_FAILURE_REGEX.search(out) is None:
            raise SubmitException(out)

    def get_status_command(self, native_ids: Collection[str]) -> List[str]:
        """See :proc:`~BatchSchedulerExecutor.get_status_command`."""
        return [
            "bjobs",
            "-o",
            "JOBID STAT EXIT_REASON KILL_REASON SUSPEND_REASON",
            "-json",
            "-a",
            *native_ids,
        ]

    def parse_status_output(self, out: str) -> Dict[str, JobStatus]:
        """See :proc:`~BatchSchedulerExecutor.parse_status_output`.

        Iterate through the RECORDS entry, grabbing JOBID and STAT entries, as well
        as any state-change reasons if present.
        """
        output = json.loads(out)
        status_map = {}
        for entry in output["RECORDS"]:
            if "ERROR" in entry:
                continue
            state = self._STATE_MAP[entry["STAT"]]
            message = None
            for reason in ("EXIT_REASON", "KILL_REASON", "SUSPEND_REASON"):
                if entry[reason]:
                    message = entry["reason"]
                    break
            status_map[entry["JOBID"]] = JobStatus(state, message=message)
        return status_map

    def job_id_from_submit_output(self, out: str) -> str:
        """See :proc:`~BatchSchedulerExecutor.job_id_from_submit_output`."""
        match = _BSUB_REGEX.search(out)
        if match is None:
            raise SubmitException(out)
        return match.group(0)[5:-1]


__PSI_J_EXECUTORS__ = [LsfJobExecutor]
