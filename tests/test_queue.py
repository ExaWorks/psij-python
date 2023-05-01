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
        "get_user_jobs": "squeue -u $(whoami)",
        "kill_command": "scancel"
    },
    "lsf": {
        "get_queues": "bqueues -u $(whoami)",
        "get_user_jobs": "bjobs",
        "kill_command": "bkill"
    }
}


def get_slurm_queues() -> None:
    res = os.popen("mdiag -c").read().split("\n")
    res = [line.split("=")[-1] for line in res if "PartitionName" in line]
    return res


def get_lsf_queues() -> None:
    res = os.popen("bqueues -u ramon").read().split("\n")
    res = [l for l in res if len(l) != 0]
    res = [l.split(" ", 1) for l in res]
    res = [l[0] for l in res if "Active" in l[1] and len(l) != 0]
    return res


def get_queue_info(executor: str) -> List[str]:
    res = []
    command = SCHEDULER_COMMANDS[executor]["get_user_jobs"]
    res.extend(os.popen(command).read().split("\n"))
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
        pytest.raises(Exception("Need at least two queues to perform this test"))
        return

    print("available queues:", queues)
    test_queues = random.sample(queues, 2)
    print("test queues:", test_queues)

    executor = JobExecutor.get_instance(scheduler)

    job1 = make_job(test_queues[0])
    executor.submit(job1)
    qstat = get_queue_info(scheduler)
    job1_qstat_entry = [l for l in qstat if job1._native_id in l][0]
    assert test_queues[0] in job1_qstat_entry

    job2 = make_job(test_queues[1])
    executor.submit(job2)
    qstat = get_queue_info(scheduler)
    job2_qstat_entry = [l for l in qstat if job2._native_id in l][0]
    assert test_queues[1] in job2_qstat_entry

    qstat = get_queue_info(scheduler)
    print("qstat = ", "\n".join(qstat))

    kill_job(scheduler, job1)
    kill_job(scheduler, job2)

    qstat = get_queue_info(scheduler)
    print("qstat = ", "\n".join(qstat))
