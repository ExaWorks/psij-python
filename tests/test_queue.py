import os
import random

import logging
from pathlib import Path

import pytest

from psij import Job, JobSpec, JobAttributes, JobExecutor, ResourceSpecV1
from tempfile import TemporaryDirectory

from executor_test_params import ExecutorTestParams
from _test_tools import _get_executor_instance, _get_timeout, assert_completed, _make_test_dir

from pprint import pprint


def get_slurm_queues():
    res = os.popen("mdiag -c").read().split("\n")
    res = [line.split("=")[-1] for line in res if "PartitionName" in line]
    return res


def get_lsf_queues():
    res = os.popen("bqueues -u ramon").read().split("\n")
    res = [l for l in res if len(l) != 0]
    res = [l.split(" ", 1) for l in res]
    res = [l[0] for l in res if "Active" in l[1] and len(l) != 0]
    return res


def get_queue_info():
    res = []
    res.extend(os.popen("bjobs").read().split("\n"))
    res.extend(os.popen("bjobs").read().split("\n"))
    return res


def make_job(queue:str) -> Job:
    return Job(
        JobSpec(
            executable="/bin/date",
            # arguments=['-utc', '--debug'],
            # resources=ResourceSpecV1(node_count=1),
            attributes=JobAttributes(
                queue_name=queue,
            ),
        )
    )


def test_queue(execparams: ExecutorTestParams) -> None:
    executor = ""
    queues = []
    slurm_queues = get_slurm_queues()
    lsf_queues = get_lsf_queues()

    queues.extend(slurm_queues)
    queues.extend(lsf_queues)

    print("slurm:", slurm_queues)
    print("lsf:", lsf_queues)
    print("extended ques:", queues)

    if len(slurm_queues) != 0:
        executor = "slurm"
    elif len(lsf_queues) != 0:
        executor = "lsf"

    if len(queues) <= 1:
        return

    test_queues = random.sample(queues, 2)
    print("test queues:", test_queues)

    print("Executor = ", executor)

    executor = JobExecutor.get_instance(executor)

    job1 = make_job(test_queues[0])
    executor.submit(job1)
    qstat = get_queue_info()
    job1_qstat_entry = [l for l in qstat if job1._native_id in l][0]
    assert test_queues[0] in job1_qstat_entry

    job2 = make_job(test_queues[1])
    executor.submit(job2)
    qstat = get_queue_info()
    job2_qstat_entry = [l for l in qstat if job2._native_id in l][0]
    assert test_queues[1] in job2_qstat_entry

    job1.wait()
    job2.wait()
    print("Job1:", job1.status)
    print("Job2:", job2.status)
    print()
