from psij import Job, JobSpec, JobExecutor
from _test_tools import assert_completed


def test_user_guide_job_arguments() -> None:
    ex = JobExecutor.get_instance('local')
    job = Job(
        JobSpec(
            executable='/bin/date',
            arguments=['-utc']
        )
    )
    ex.submit(job)
    status = job.wait()
    assert_completed(job, status)
