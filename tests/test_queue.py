import os
import random

import logging
from pathlib import Path
from typing import List 

import pytest

from psij import Job, JobSpec, JobAttributes, JobExecutor, ResourceSpecV1
from tempfile import TemporaryDirectory

from executor_test_params import ExecutorTestParams
from _test_tools import _get_executor_instance, _get_timeout, assert_completed, _make_test_dir


SCHEDULER_COMMANDS = {
    "slurm": {
        "get_queues": "mdiag -c",
        "get_user_jobs": "squeue -o '%P' --jobs",
        "kill_command": "scancel"
    },
    "lsf": {
        "get_queues": "bqueues -u $(whoami) -o 'QUEUE_NAME NJOBS PEND RUN SUSP STATUS'",
        "get_user_jobs": "bjobs -o 'queue'",
        "kill_command": "bkill"
    }
}


def get_slurm_queues() -> List[str]:
    command = SCHEDULER_COMMANDS["slurm"]["get_queues"]
    out = os.popen(command).read().split("\n")
    return [line.split("=")[-1] for line in out if "PartitionName" in line]


def get_lsf_queues() -> List[str]:
    valid_queues = []
    command = SCHEDULER_COMMANDS["lsf"]["get_queues"]
    out = os.popen(command).read().split("\n")
    out = [l for l in out if len(l) != 0]
    queues = [l.split(" ") for l in out]
    if len(queues) == 0:
        return []
    queues.pop(0) # popping headers 

    for queue_info in queues: 
        name = queue_info[0]
        njobs = int(queue_info[1])
        pend = int(queue_info[2])
        run = int(queue_info[3])
        susp = int(queue_info[4])
        status = str(queue_info[5])

        if "active" not in status.lower():
            continue

        if (njobs + pend + run + susp) > 10:
            valid_queues.append(name)

    return valid_queues


def get_queue_info(executor: str, job: Job) -> List[str]:
    res = []
    command = SCHEDULER_COMMANDS[executor]["get_user_jobs"]
    res.extend(os.popen(f"{command} {job._native_id}").read().split("\n"))
    return res


def kill_job(scheduler: str, job: Job) -> None:
    command = f"{SCHEDULER_COMMANDS[scheduler]['kill_command']} {job._native_id}"
    print("Kill command:", command)
    os.system(command)


def make_job(queue:str) -> Job:
    return Job(
        JobSpec(
            executable="/bin/date",
            attributes=JobAttributes(
                queue_name=queue,
            ),
        )
    )


def test_queue(execparams: ExecutorTestParams) -> None:
    scheduler = ""
    queues = []
    slurm_queues = get_slurm_queues()
    lsf_queues = get_lsf_queues()

    queues.extend(slurm_queues)
    queues.extend(lsf_queues)

    if len(slurm_queues) != 0:
        scheduler = "slurm"
    elif len(lsf_queues) != 0:
        scheduler = "lsf"

    if len(queues) < 2:
        pytest.skip("Need at least two queues to perform this test")
        return

    if execparams.launcher != "single":
        pytest.skip("No need to test non-single launchers")

    print("available queues:", queues)
    test_queues = random.sample(queues, 2)
    print("test queues:", test_queues)

    executor = JobExecutor.get_instance(scheduler)

    job1 = make_job(test_queues[0])
    executor.submit(job1)
    qstat = get_queue_info(scheduler, job1)
    assert test_queues[0] in qstat

    job2 = make_job(test_queues[1])
    executor.submit(job2)
    qstat = get_queue_info(scheduler, job2)
    assert test_queues[1] in qstat

    kill_job(scheduler, job1)
    kill_job(scheduler, job2)
