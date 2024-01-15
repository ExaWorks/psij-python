from datetime import timedelta

from _test_tools import _get_executor_instance, _get_timeout, assert_completed
from executor_test_params import ExecutorTestParams
from psij import Job, JobSpec, JobAttributes


def test_issue_435(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/date', launcher=execparams.launcher,
                      attributes=JobAttributes(duration=timedelta(seconds=3700.5))))
    ex = _get_executor_instance(execparams, job)
    ex.submit(job)
    status = job.wait(timeout=_get_timeout(execparams))
    assert_completed(job, status)
