# Quick start guide

This document will guide you through the install procedure and your first hello world example.

- [Requirements](#requirements)
- [Install psi-j](#install-psj-j)
- [Hello World example](#hello-world)

## Requirements
- python3.7

## Install psi-j

1. Clone repository into your working directory:
    `git clone https://github.com/ExaWorks/psi-j-python.git`

2. `cd psi-j-python`
3. `make install`

If you have conda installed you might want to start from a fresh environment:

1. `conda create -n psi-j python=3.7`
2. `conda activate psi-j`
3. follow the steps above





## Hello world

**Requirements**
- python3.7
- job executioner, e.g. slurm in this example

**Steps**

1. Create a file *my-worklfow.py* and copy and paste the code below:

```python

import psij

jex = psij.JobExecutor.get_instance('slurm')

N=1 # number of jobs to run

def make_job():
    job = psij.Job()
    spec = psij.JobSpec()
    spec.executable = '/bin/sleep'
    spec.arguments = ['10']
    job.spec = spec
    return job

jobs = []
for i in range(N):
    job = make_job()
    jobs.append(job)
    jex.submit(job)

for i in range(N):
    jobs[i].wait()

```
2. In this example the number of jobs is 1. Set *N* to the number of jobs you want to run and save file.

3. `python my-workflow.py`
 