from psij import Job, JobSpec, JobExecutor, JobStatus, JobState
from _test_tools import assert_completed


def test_user_guide_callbacks() -> None:
    ex = JobExecutor.get_instance('local')
    job = Job(JobSpec('/bin/date'))

    def callback(job: Job, status: JobStatus) -> None:
        if status.state == JobState.ACTIVE:
            print('Job %s is running' % job)
        elif status.state.final:
            print('Job %s has finished' % job)

    job.set_job_status_callback(callback)
    ex.submit(job)
    status = job.wait()
    assert_completed(job, status)
