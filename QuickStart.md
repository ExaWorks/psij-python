# Quick Start Guide

This document will guide you through the install procedure and your first hello world example.

- [Requirements](#requirements)
- [Install psij](#install-psij)
- [Hello World example](#hello-world)

## Requirements
- python3.7+

## Install psij

If you have conda installed you might want to start from a fresh environment. This part is not installing psij but setting up a new environment with the specified python version:

1. `conda create -n psij python=3.7`
2. `conda activate psij`


Install psij from the GitHub repository:

1. Clone the repository into your working directory:

    `git clone https://github.com/ExaWorks/psij-python.git`

2. `cd psij-python`
3. `pip install .`







## Hello World

**Requirements**
- python3.7
- Job executor, e.g. Slurm in this example

**Steps**

1. Create a file *my-workflow.py* and copy and paste this code:

```python

import psij

jex = psij.JobExecutor.get_instance('slurm')

N=1 # number of jobs to run

def make_job():
    job = psij.Job()
    spec = psij.JobSpec()
    
    spec.executable = 'echo'
    spec.arguments = ['HELLO WORLD!']
    
    # set project name if no default is specified
    # spec.attributes.project_name = <PROJECT_NAME>
    
    # set queue if no default is specified
    # spec.attributes.queue_name = <QUEUE_NAME>
  
    spec.stdout_path = "out.txt"
    
    # set node count
    # resource = psij.ResourceSpecV1()
    # resource.node_count = N
    
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
2. In this example the number of jobs is 1. Set *N* to the number of jobs you want to run and save the file.

3. `python my-workflow.py`
