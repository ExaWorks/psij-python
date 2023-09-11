from psij import Job, JobSpec, JobExecutor
from _test_tools import assert_completed


def test_user_guide_plain_job() -> None:
    ex = JobExecutor.get_instance('local')
    job = Job(JobSpec(executable='/bin/date'))
    ex.submit(job)
    status = job.wait()
    assert_completed(job, status)
