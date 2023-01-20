from psij import Job, JobSpec, JobExecutor
from executor_test_params import ExecutorTestParams


def test_getting_started_job_arguements(execparams: ExecutorTestParams) -> None:
    ex = JobExecutor.get_instance(execparams.executor)
    job = Job(JobSpec(executable='/bin/date', arguments=['-utc', '--debug']))
    ex.submit(job)
