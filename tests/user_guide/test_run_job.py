from psij import Job, JobSpec, JobExecutor


def test_user_guide_plain_job() -> None:
    # DOC: start
    ex = JobExecutor.get_instance('local')
    job = Job(JobSpec('/bin/date'))
    try:
        ex.run(job)
        print('Job succeeded')
    except Exception as ex:
        print(f'Job failed: {ex}')
        # DOC: end
        raise
