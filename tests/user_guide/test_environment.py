from psij import Job, JobSpec, JobExecutor
from _test_tools import assert_completed


def test_user_guide_environment() -> None:
    ex = JobExecutor.get_instance('local')
    # DOC: start
    job = Job(
        JobSpec(
            executable='/bin/date',
            environment={'TZ': 'America/Los_Angeles'}
        )
    )
    # DOC: end
    ex.submit(job)
    status = job.wait()
    assert_completed(job, status)
