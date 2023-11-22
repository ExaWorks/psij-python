from executor_test_params import ExecutorTestParams

from _test_tools import assert_completed, _get_executor_instance


def test_getting_started_single_job(execparams: ExecutorTestParams) -> None:
    from psij import Job, JobSpec

    job = Job(JobSpec(executable="/bin/date"))
    ex = _get_executor_instance(execparams, job)
    ex.submit(job)

    status = job.wait()
    assert_completed(job, status)
