from psij import Job, JobSpec, JobExecutor


def submit() -> None:
    # DOC: start
    ex = JobExecutor.get_instance('local')
    job = Job(JobSpec('/bin/sleep', ['10']))
    ex.submit(job)
    assert job.native_id is not None
    print(job.native_id)
    # DOC: end


if __name__ == '__main__':
    submit()
