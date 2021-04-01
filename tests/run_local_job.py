#!/usr/bin/env python3

# This is meant as a simple test file to check if psi/j was installed successfully

import sys

from psi.j import Job, JobExecutor, JobSpec


if __name__ == '__main__':
    url = 'local'
    if len(sys.argv) > 1:
        url = sys.argv[1]
    job = Job(JobSpec(executable='/bin/date'))
    exec = JobExecutor.get_instance(url)
    exec.submit(job)
    print('Job submitted')
    status = job.wait()
    print('Job done: {}'.format(status))
