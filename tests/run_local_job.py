# This is meant as a simple test file to check if psi/j was installed successfully

from psi.j import SubmitException, Job, JobExecutor, JobSpec, JobState


if __name__ == '__main__':
    job = Job(JobSpec(executable='/bin/date'))
    exec = JobExecutor.get_instance('local')
    exec.submit(job)
    print('Job submitted')
    status = job.wait()
    print('Job done: {}'.format(status))
