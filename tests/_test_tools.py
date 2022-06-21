from datetime import timedelta
from pathlib import Path
from typing import Optional

from executor_test_params import ExecutorTestParams

from psij import JobStatus, JobState, Job, JobExecutor, JobAttributes

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


def assert_completed(job: Job, status: Optional[JobStatus]) -> None:
    assert status is not None
    if status.state != JobState.COMPLETED:
        assert job.spec is not None
        stdout = _read_file(job.spec.stdout_path)
        stderr = _read_file(job.spec.stderr_path)
        raise AssertionError('Job not completed. Status message: %s, stdout: %s, stderr: %s'
                             % (status.message, stdout, stderr))


def _get_executor_instance(ep: ExecutorTestParams, job: Job) -> JobExecutor:
    assert job.spec is not None
    job.spec.launcher = ep.launcher
    job.spec.attributes = JobAttributes(custom_attributes=ep.custom_attributes)
    return JobExecutor.get_instance(ep.executor, url=ep.url)
