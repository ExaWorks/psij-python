from psij import Job, JobSpec, JobExecutor

from _test_tools import assert_completed


def test_user_guide_multiple_jobs() -> None:
    ex = JobExecutor.get_instance('local')
    spec = JobSpec('/bin/sleep', ['5'])

    job_1 = Job(spec)
    ex.submit(job_1)

    job_2 = Job(spec)
    ex.submit(job_2)

    status1 = job_1.wait()
    status2 = job_2.wait()

    assert_completed(job_1, status1)
    assert_completed(job_2, status2)
