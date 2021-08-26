#!/usr/bin/env python3

# This is meant as a simple test file to check if psij was installed successfully

import sys

from psij import Job, JobExecutor, JobSpec


if __name__ == '__main__':
    name = 'local'
    if len(sys.argv) > 1:
        name = sys.argv[1]
    jobs = list()
    job = Job(JobSpec(executable='/bin/date'))
    exec = JobExecutor.get_instance(name)
    exec.submit(job)
    jobs.append(job)
    print('Job submitted')
    status = job.wait()
    print('Job done: {}'.format(status))
