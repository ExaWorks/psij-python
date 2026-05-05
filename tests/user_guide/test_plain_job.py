from psij import Job, JobSpec, JobExecutor
from _test_tools import assert_completed


def test_user_guide_plain_job() -> None:
    # DOC: start submitting
    ex = JobExecutor.get_instance('local')
    # DOC: start job
    job = Job(JobSpec(executable='/bin/date'))
    # DOC: end job
    ex.submit(job)
    # DOC: end submitting
    status = job.wait()
    assert_completed(job, status)
