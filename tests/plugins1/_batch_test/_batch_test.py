import sys
from pathlib import Path
from typing import Optional, Collection, List, Dict, IO, cast

from psij import Job, JobStatus, JobState, SubmitException, JobExecutorConfig, ResourceSpecV1
from psij.executors.batch.batch_scheduler_executor import BatchSchedulerExecutor, \
    BatchSchedulerExecutorConfig, InvalidJobStateError, check_status_exit_code
from psij.executors.batch.script_generator import TemplatedScriptGenerator
from psij.launchers import MultipleLauncher

QSUB_PATH = str(Path(__file__).parent / 'test' / 'qsub')
QSTAT_PATH = str(Path(__file__).parent / 'test' / 'qstat')
QDEL_PATH = str(Path(__file__).parent / 'test' / 'qdel')


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

        assert isinstance(self.work_directory, Path)


class _TestJobExecutor(BatchSchedulerExecutor):
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
        self.generator = TemplatedScriptGenerator(config, Path(__file__).parent / 'test'
                                                  / 'test.mustache')

    def generate_submit_script(self, job: Job, context: Dict[str, object],
                               submit_file: IO[str]) -> None:
        self.generator.generate_submit_script(job, context, submit_file)

    def get_submit_command(self, job: Job, submit_file_path: Path) -> List[str]:
        return [sys.executable, QSUB_PATH, str(submit_file_path.absolute())]

    def get_cancel_command(self, native_id: str) -> List[str]:
        return [sys.executable, QDEL_PATH, native_id]

    def process_cancel_command_output(self, exit_code: int, out: str) -> None:
        if exit_code == 16:
            raise InvalidJobStateError()
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

    def get_list_command(self) -> List[str]:
        return [sys.executable, QSTAT_PATH]

    def _get_state(self, state: str) -> JobState:
        assert state in _TestJobExecutor._STATE_MAP
        return _TestJobExecutor._STATE_MAP[state]

    def _clean_submit_script(self, job: Job):
        super()._clean_submit_script(job)
        self._delete_aux_file(job, '.nodefile')


class _TestLauncher(MultipleLauncher):
    def __init__(self, config: Optional[JobExecutorConfig] = None):
        super().__init__(Path(__file__).parent / 'test' / 'launcher.sh', config)

    def _files_to_deploy(self) -> List[Path]:
        files = super()._files_to_deploy()
        files.append(Path(__file__).parent / 'test' / 'hostname')
        return files

    def get_additional_args(self, job: Job) -> List[str]:
        args = super().get_additional_args(job)
        process_count = int(args[0])
        node_count = self._get_node_count(job)
        ppn = process_count // node_count
        if node_count * ppn != process_count:
            raise ValueError('Cannot divide processes evenly across nodes')
        args += [str(node_count), str(ppn)]
        return args

    def _get_node_count(self, job):
        assert job.spec is not None
        res = job.spec.resources
        if res is None:
            return 1
        if res.version == 1:
            res1 = cast(ResourceSpecV1, res)
            return res1.computed_node_count
        else:
            raise ValueError('This launcher cannot handle resource specs with version {}'.
                             format(res.version))
