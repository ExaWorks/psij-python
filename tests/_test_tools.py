import os
import shutil
import tempfile
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Optional, Union, Iterator

from executor_test_params import ExecutorTestParams

from psij import JobStatus, JobState, Job, JobExecutor, JobAttributes, ResourceSpecV1

_QUICK_EXECUTORS = set(['local', 'batch-test'])


def _make_test_dir() -> None:
    (Path.home() / '.psij' / 'test').mkdir(parents=True, exist_ok=True)


def _get_timeout(execparams: ExecutorTestParams) -> Optional[timedelta]:
    if execparams.executor in _QUICK_EXECUTORS:
        return timedelta(minutes=10)
    else:
        return None


def _read_file(path: Optional[Path]) -> str:
    if path is None:
        return ''

    with open(path, 'r') as f:
        return f.read()


def assert_completed(job: Job, status: Optional[JobStatus], attached: bool = False) -> None:
    assert status is not None
    if status.state != JobState.COMPLETED:
        if not attached:
            assert job.spec is not None
            stdout = _read_file(job.spec.stdout_path)
            stderr = _read_file(job.spec.stderr_path)
            raise AssertionError('Job not completed. Exit code: %s, Status message: %s, '
                                 'stdout: %s, stderr: %s'
                                 % (status.exit_code, status.message, stdout, stderr))
        else:
            raise AssertionError('Job not completed. Exit code: %s, Status message: %s'
                                 % (status.exit_code, status.message))


def _get_executor_instance(ep: ExecutorTestParams, job: Optional[Job] = None) -> JobExecutor:
    if job is not None:
        assert job.spec is not None
        job.spec.launcher = ep.launcher
        attrs = JobAttributes(custom_attributes=ep.custom_attributes)
        job.spec.attributes = attrs
        if ep.account is not None:
            attrs.account = ep.account
        res = job.spec.resources
        if ep.queue_name is not None:
            attrs.queue_name = ep.queue_name
        if (res and isinstance(res, ResourceSpecV1) and res.computed_node_count > 1
                and ep.multi_node_queue_name is not None):
            attrs.queue_name = ep.multi_node_queue_name
    return JobExecutor.get_instance(ep.executor, url=ep.url)


@contextmanager
def _deploy(path: Union[Path, str]) -> Iterator[Path]:
    # Copies `path` to a directory assumed to be on a shared FS (~/.psij/test) and
    # returns the resulting path
    if isinstance(path, str):
        path = Path(path)
    with tempfile.NamedTemporaryFile(dir=Path.home() / '.psij' / 'test', delete=False) as df:
        try:
            df.close()
            shutil.copyfile(path, df.name)
            yield Path(df.name)
        finally:
            os.unlink(df.name)
