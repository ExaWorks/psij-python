import logging

from psi.j import Job, JobExecutor, JobSpec, JobState


logging.basicConfig(level=logging.DEBUG)


if __name__ == "__main__":
    job = Job(JobSpec(executable='/bin/date'))
    exec = JobExecutor.get_instance('local')
    exec.submit(job)
    job.wait()

    job = Job(JobSpec(executable='/bin/sleep', arguments=['1']))
    exec = JobExecutor.get_instance('local')
    exec.submit(job)
    job.wait(target_states=[JobState.ACTIVE])
    native_id = job.native_id

    assert native_id is not None

    job2 = Job()
    exec.attach(job2, native_id)
    job2.wait()
