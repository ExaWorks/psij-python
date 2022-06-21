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


def assert_completed(status: Optional[JobStatus]) -> None:
    assert status is not None
    if status.state != JobState.COMPLETED:
        raise AssertionError('Job not completed. Status message: %s' % status.message)


def _get_executor_instance(ep: ExecutorTestParams, job: Job) -> JobExecutor:
    assert job.spec is not None
    job.spec.launcher = ep.launcher
    job.spec.attributes = JobAttributes(custom_attributes=ep.custom_attributes)
    return JobExecutor.get_instance(ep.executor, url=ep.url)
