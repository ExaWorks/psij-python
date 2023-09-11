from psij import Job, JobSpec, JobExecutor, JobState


def test_user_guide_plain_job() -> None:
    ex = JobExecutor.get_instance('local')
    job = Job(JobSpec(executable='/bin/date'))
    ex.submit(job)
    status = job.wait()
    assert status is not None
    assert status.state == JobState.COMPLETED
