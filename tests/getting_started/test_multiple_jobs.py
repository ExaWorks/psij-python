from psij import Job, JobSpec, JobExecutor
from executor_test_params import ExecutorTestParams


def test_getting_started_multiple_jobs(execparams: ExecutorTestParams) -> None:
    ex = JobExecutor.get_instance(execparams.executor)
    for _ in range(10):
        job = Job(JobSpec(executable="/bin/date"))
        ex.submit(job)
