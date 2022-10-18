#!/usr/bin/env python3

# This is meant as a simple test file to check if psij was installed successfully

import sys

from psij import Job, JobExecutor, JobSpec, JobStatus


def job_status_changed(job: Job, status: JobStatus) -> None:
    print('Job {}: {}'.format(job.id, status))


if __name__ == '__main__':
    name = 'local'
    url = None

    if len(sys.argv) > 1:
        name = sys.argv[1]

    if len(sys.argv) > 2:
        url = sys.argv[2]

    jobs = list()
    job = Job(JobSpec(executable='/bin/date'))
    job.set_job_status_callback(job_status_changed)
    ex = JobExecutor.get_instance(name=name, url=url)
    ex.submit(job)
    jobs.append(job)
    print('Job submitted')
    status = job.wait()
    print('Job done: {}'.format(status))
