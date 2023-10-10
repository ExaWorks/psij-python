from datetime import timedelta

from psij import Job, JobExecutor, JobSpec, JobState


def _test_wait() -> None:
    ex = JobExecutor.get_instance('local')
    job = Job(JobSpec('/bin/sleep', ['4']))
    ex.submit(job)
    status = job.wait(target_states=JobState.ACTIVE)
    assert status is not None
    assert status.state == JobState.ACTIVE

    status = job.wait(target_states=JobState.QUEUED)
    assert status is not None
    assert status.state == JobState.ACTIVE

    status = job.wait(timedelta(milliseconds=100))
    assert status is None

    status = job.wait()
    assert status is not None
    assert status.state == JobState.COMPLETED

    status = job.wait(target_states=JobState.QUEUED)
    assert status is not None
    assert status.state == JobState.COMPLETED

    status = job.wait(target_states=JobState.FAILED)
    assert status is not None
    assert status.state == JobState.COMPLETED
