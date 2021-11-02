import sys
from distutils.version import StrictVersion
from pathlib import Path
from typing import Optional, Collection, List, Dict, TextIO

from psij import Job, JobStatus, JobState, SubmitException
from psij.executors.batch.batch_scheduler_executor import BatchSchedulerExecutor, \
    BatchSchedulerExecutorConfig, _InvalidJobStateError, check_status_exit_code
from psij.executors.batch.script_generator import TemplatedScriptGenerator


QSUB_PATH = str(Path(__file__).parent / 'batch' / 'test' / 'qsub')
QSTAT_PATH = str(Path(__file__).parent / 'batch' / 'test' / 'qstat')
QDEL_PATH = str(Path(__file__).parent / 'batch' / 'test' / 'qdel')


class _TestExecutorConfig(BatchSchedulerExecutorConfig):
    """A configuration class for the test batch executor."""

    def __init__(self, launcher_log_file: Optional[Path] = None,
                 work_directory: Optional[Path] = None, queue_polling_interval: int = 1,
                 initial_queue_polling_delay: int = 1, queue_polling_error_threshold: int = 2,
                 keep_files: bool = False):
        """Initializes a `TestExecutorConfig`.

        This constructor overrides the constructor for :class:`~BatchSchedulerExecutorConfig` to
        change the `queue_polling_interval` default to 5 seconds.
        """
        super().__init__(launcher_log_file, work_directory, queue_polling_interval,
                         initial_queue_polling_delay, queue_polling_error_threshold, keep_files)


class _TestJobExecutor(BatchSchedulerExecutor):
    _NAME_ = 'batch-test'
    _VERSION_ = StrictVersion('0.0.1')

    _STATE_MAP = {
        'F': JobState.FAILED,
        'X': JobState.CANCELED,
        'C': JobState.COMPLETED,
        'Q': JobState.QUEUED,
        'R': JobState.ACTIVE,
    }

    def __init__(self, url: Optional[str] = None, config: Optional[_TestExecutorConfig] = None):
        if not config:
            config = _TestExecutorConfig()
        super().__init__(config=config)
        self.generator = TemplatedScriptGenerator(config, Path(__file__).parent / 'batch' / 'test'
                                                  / 'test.mustache')

    def generate_submit_script(self, job: Job, context: Dict[str, object],
                               submit_file: TextIO) -> None:
        self.generator.generate_submit_script(job, context, submit_file)

    def get_submit_command(self, job: Job, submit_file_path: Path) -> List[str]:
        return [sys.executable, QSUB_PATH, str(submit_file_path.absolute())]

    def get_cancel_command(self, native_id: str) -> List[str]:
        return [sys.executable, QDEL_PATH, native_id]

    def process_cancel_command_output(self, exit_code: int, out: str) -> None:
        if exit_code == 16:
            raise _InvalidJobStateError()
        else:
            raise SubmitException(out)

    def get_status_command(self, native_ids: Collection[str]) -> List[str]:
        ids = ','.join(native_ids)
        return [sys.executable, QSTAT_PATH, ids]

    def job_id_from_submit_output(self, out: str) -> str:
        return out.strip().split()[-1]

    def parse_status_output(self, exit_code: int, out: str) -> Dict[str, JobStatus]:
        check_status_exit_code(QSTAT_PATH, exit_code, out)
        r = {}
        lines = iter(out.split('\n'))
        for line in lines:
            if not line:
                continue
            cols = line.split(maxsplit=2)
            native_id = cols[0]
            state = self._get_state(cols[1])
            msg = cols[2] if len(cols) == 3 else None
            r[native_id] = JobStatus(state, message=msg)
        return r

    def _get_state(self, state: str) -> JobState:
        assert state in _TestJobExecutor._STATE_MAP
        return _TestJobExecutor._STATE_MAP[state]


__PSI_J_EXECUTORS__ = [_TestJobExecutor]
