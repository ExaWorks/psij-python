"""Defines a JobExecutor for the Cobalt resource manager."""
from datetime import timedelta
from pathlib import Path
from typing import Optional, Collection, List, Dict, IO
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
    """A :class:`~psij.JobExecutor` for the Cobalt Workload Manager.

    The `Cobalt HPC Job Scheduler <https://xgitlab.cels.anl.gov/aig-public/cobalt>`_,
    is used by `Argonne's <www.anl.gov>`_ `ALCF <www.alcf.anl.gov>`_ systems.

    Uses the ``qsub``, ``qstat``, and ``qdel`` commands, respectively, to submit,
    monitor, and cancel jobs.

    Creates a batch script with #COBALT directives when submitting a job.

    Custom attributes prefixed with `cobalt.` are rendered as long-form directives in the script.
    For example, setting `custom_attributes['cobalt.m'] = 'co'` results in the `#COBALT --m=co`
    directive being placed in the submit script.
    """

    # see https://Cobalt.schedmd.com/squeue.html
    _STATE_MAP = {
        "starting": JobState.ACTIVE,
        "queued": JobState.QUEUED,
        "running": JobState.ACTIVE,
        "exiting": JobState.ACTIVE,
        "killing": JobState.FAILED,
    }

    def __init__(self, url: Optional[str] = None,
                 config: Optional[CobaltExecutorConfig] = None) -> None:
        """
        Parameters
        ----------
        url
            This parameter is not used and is only provided for compatibility reasons.
        config
            An optional configuration for this executor.
        """
        if not config:
            config = CobaltExecutorConfig()
        super().__init__(config=config)
        self.generator = TemplatedScriptGenerator(
            config, Path(__file__).parent / "cobalt" / "cobalt.mustache"
        )

    def generate_submit_script(self, job: Job, context: Dict[str, object],
                               submit_file: IO[str]) -> None:
        """See :meth:`~.BatchSchedulerExecutor.generate_submit_script`."""
        self.generator.generate_submit_script(job, context, submit_file)

    def get_submit_command(self, job: Job, submit_file_path: Path) -> List[str]:
        """See :meth:`~.BatchSchedulerExecutor.get_submit_command`."""
        str_path = str(submit_file_path.absolute())
        os.chmod(str_path, os.stat(str_path).st_mode | stat.S_IEXEC)
        return ["qsub", str_path]

    def get_cancel_command(self, native_id: str) -> List[str]:
        """See :meth:`~.BatchSchedulerExecutor.get_cancel_command`."""
        return ["qdel", native_id]

    def process_cancel_command_output(self, exit_code: int, out: str) -> None:
        """See :meth:`~.BatchSchedulerExecutor.process_cancel_command_output`.

        This should be unnecessary because `qdel` only seems to fail on
        non-integer job IDs.
        """
        raise SubmitException("Failed job cancel job: %s" % out)

    def get_status_command(self, native_ids: Collection[str]) -> List[str]:
        """See :meth:`~.BatchSchedulerExecutor.get_status_command`."""
        return [_QSTAT_COMMAND, "-l", "--header=Jobid:State", *native_ids]

    def parse_status_output(self, exit_code: int, out: str) -> Dict[str, JobStatus]:
        """See :meth:`~.BatchSchedulerExecutor.parse_status_output`."""
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

    def get_list_command(self) -> List[str]:
        """See :meth:`~.BatchSchedulerExecutor.get_list_command`."""
        return [_QSTAT_COMMAND, '-u', self._current_user(), '--header', 'JobId']

    def job_id_from_submit_output(self, out: str) -> str:
        """See :meth:`~.BatchSchedulerExecutor.job_id_from_submit_output`."""
        match = _QSUB_REGEX.search(out)
        if match is None:
            raise SubmitException(out)
        return match.group(0)

    def _format_duration(self, d: timedelta) -> str:
        # https://trac.mcs.anl.gov/projects/cobalt/wiki/qsub.1.html:
        #   The time may be specified as eitehr an integer number of minutes or a colon-delimited
        #   value of the format: HH:MM:SS. Enter 0 to get the max allowed walltime.
        # base class _format_duration is HH:MM:SS
        return super()._format_duration(d)
