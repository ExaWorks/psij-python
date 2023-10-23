from psij import Job, JobSpec, JobExecutor, JobState


def test_user_guide_job_wait_active() -> None:
    ex = JobExecutor.get_instance('local')
    job = Job(JobSpec(executable='/bin/date'))
    ex.submit(job)
    status = job.wait(target_states=[JobState.ACTIVE])
    assert status is not None
    assert status.state == JobState.ACTIVE
