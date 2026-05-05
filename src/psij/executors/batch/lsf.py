"""Defines the LsfJobExecutor class and its config class."""
from datetime import timedelta
from pathlib import Path
import re
import json
from typing import Collection, List, Dict, Iterable, Tuple, Type

from psij import JobStatus, JobState, SubmitException
from psij.base_job import BaseJob
from psij.executors.batch.batch_scheduler_executor import (
    BatchSchedulerExecutorConfig,
    check_status_exit_code, AsyncBatchSchedulerExecutor,
    BatchScheduler, SyncBatchSchedulerExecutor,
)
from psij.executors.batch.script_generator import TemplatedScriptGenerator


_BKILL_FAILURE_REGEX = re.compile(
    r"(no matching job)|(already finished)", re.IGNORECASE
)
_BSUB_REGEX = re.compile(r"Job <[0-9]+>", re.IGNORECASE)
_BJOBS_COMMAND = "bjobs"


class LsfExecutorConfig(BatchSchedulerExecutorConfig):
    """A configuration class for the LSF executor."""


class LsfScheduler(BatchScheduler):
    """A :class:`~.BatchScheduler` for the LSF Workload Manager.

    The `IBM Spectrum LSF workload manager <https://www.ibm.com/docs/en/spectrum-lsf>`_
    is the system resource manager on LLNL's Sierra and Lassen, and ORNL's Summit.

    Uses the 'bsub', 'bjobs', and 'bkill' commands, respectively, to submit,
    monitor, and cancel jobs.

    Creates a batch script with #BSUB directives when submitting a job.

    Renders all custom attributes of the form `lsf.<name>` into the corresponding
    LSF directive. For example, setting
    `job.spec.attributes.custom_attributes['lsf.core_isolation'] = '0' results in a
    `#BSUB -core_isolation 0` directive being placed in the submit script.
    """

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

    def __init__(self, config: LsfExecutorConfig):
        """
        Parameters
        ----------
        config
            A configuration to use for this instance.
        """
        self.generator = TemplatedScriptGenerator(
            config, Path(__file__).parent / "lsf" / "lsf.mustache"
        )

    def generate_submit_script(self, job: BaseJob, context: Dict[str, object]) -> Iterable[str]:
        """See :meth:`~.BatchScheduler.generate_submit_script`."""
        assert job.spec is not None
        context["job_duration"] = int(job.spec.attributes.duration.total_seconds() // 60)
        return self.generator.render(job, context)

    def get_submit_command(self, job: BaseJob, submit_file_path: Path) -> List[str]:
        """See :meth:`~.BatchScheduler.get_submit_command`."""
        return ["bsub", str(submit_file_path.absolute())]

    def get_cancel_command(self, native_id: str) -> List[str]:
        """See :meth:`~.BatchScheduler.get_cancel_command`.

        ``bkill`` will exit with an error set if the job does not exist
        or has already finished.
        """
        return ["bkill", native_id]

    def process_cancel_command_output(self, exit_code: int, out: str) -> None:
        """See :meth:`~.BatchScheduler.process_cancel_command_output`.

        Check if the error was raised only because a job already exited.
        """
        if _BKILL_FAILURE_REGEX.search(out) is None:
            raise SubmitException(out)

    def get_status_command(self, native_ids: Collection[str]) -> List[str]:
        """See :meth:`~.BatchScheduler.get_status_command`."""
        return [
            _BJOBS_COMMAND,
            "-o",
            "JOBID STAT EXIT_REASON KILL_REASON SUSPEND_REASON",
            "-json",
            "-a",
            *native_ids,
        ]

    def parse_status_output(self, exit_code: int, out: str) -> Dict[str, JobStatus]:
        """See :meth:`~.BatchScheduler.parse_status_output`.

        Iterate through the RECORDS entry, grabbing JOBID and STAT entries, as well
        as any state-change reasons if present.
        """
        check_status_exit_code(_BJOBS_COMMAND, exit_code, out)
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
        """See :meth:`~.BatchScheduler.job_id_from_submit_output`."""
        match = _BSUB_REGEX.search(out)
        if match is None:
            raise SubmitException(out)
        return match.group(0)[5:-1]

    def get_list_command(self) -> List[str]:
        """See :meth:`~.BatchScheduler.get_list_command`."""
        return [_BJOBS_COMMAND, '-a', '-noheader', '-o', 'jobid', '-u', self._current_user()]

    def _format_duration(self, d: timedelta) -> str:
        # https://www.ibm.com/docs/en/spectrum-lsf/10.1.0?topic=o-w-1:
        #   bsub -W [hour:]minute[/host_name | /host_model]
        return "%s:%s" % (int(d.total_seconds()) // 3600, (d.seconds // 60) % 60)


class LsfJobExecutor(SyncBatchSchedulerExecutor):
    """Synchronous job executor for LSF."""

    def get_concrete_classes(self) \
            -> Tuple[Type[BatchScheduler], Type[BatchSchedulerExecutorConfig]]:
        return LsfScheduler, LsfExecutorConfig


class AsyncLsfJobExecutor(AsyncBatchSchedulerExecutor):
    """Asynchronous job executor for LSF."""

    def get_concrete_classes(self) \
            -> Tuple[Type[BatchScheduler], Type[BatchSchedulerExecutorConfig]]:
        return LsfScheduler, LsfExecutorConfig
