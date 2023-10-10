from psij import Job, JobSpec, JobExecutor
from _test_tools import assert_completed


def test_user_guide_simple_job_with_props() -> None:
    ex = JobExecutor.get_instance('local')

    spec = JobSpec()
    spec.executable = '/bin/date'
    spec.arguments = ['--utc']
    job = Job(spec)

    ex.submit(job)
    status = job.wait()
    assert_completed(job, status)
