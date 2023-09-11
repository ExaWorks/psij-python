from executor_test_params import ExecutorTestParams

from _test_tools import assert_completed


def test_getting_started_single_job(execparams: ExecutorTestParams) -> None:
    from psij import Job, JobSpec, JobExecutor

    ex = JobExecutor.get_instance(execparams.executor)
    job = Job(JobSpec(executable="/bin/date"))
    ex.submit(job)

    status = job.wait()
    assert_completed(job, status)
