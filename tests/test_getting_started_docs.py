"""Functions for testing the various code snippets available in psij docs - 'getting started'."""
from time import sleep
from psij import Job, JobSpec, JobStatus
from executor_test_params import ExecutorTestParams
from _test_tools import _get_executor_instance, _get_timeout, assert_completed

status_callback_job_count = 3


def test_getting_started_basic_usage(execparams: ExecutorTestParams) -> None:
    job = Job(
        JobSpec(
            executable="/bin/date",
            launcher=execparams.launcher
        )
    )
    ex = _get_executor_instance(execparams, job)
    ex.submit(job)
    status = job.wait(timeout=_get_timeout(execparams))
    assert_completed(job, status)


def test_getting_started_adding_complexity(execparams: ExecutorTestParams) -> None:
    num_jobs = 3
    for _ in range(num_jobs):
        job = Job(
            JobSpec(
                executable="/bin/date",
                launcher=execparams.launcher
            )
        )
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)


def test_getting_started_status_callbacks(execparams: ExecutorTestParams) -> None:
    def callback(job: Job, status: JobStatus) -> None:
        global status_callback_job_count
        if status.final:
            print(f"Job {job} completed with status {status}")
            status_callback_job_count -= 1

    for _ in range(status_callback_job_count):
        job = Job(JobSpec(executable='/bin/date', launcher=execparams.launcher))
        ex = _get_executor_instance(execparams, job)
        ex.set_job_status_callback(callback)
        ex.submit(job)

    while status_callback_job_count > 0:
        sleep(0.01)


def test_our_test(execparams: ExecutorTestParams) -> None:
    num_jobs = 3

    def make_job() -> Job:
        job = Job()
        spec = JobSpec()
        spec.executable = 'echo'
        spec.arguments = ['HELLO WORLD!']
        job.spec = spec
        return job

    jobs = []
    for _ in range(num_jobs):
        job: Job = make_job()
        jobs.append(job)
        jex = _get_executor_instance(execparams, job)
        jex.submit(job)

    for job in jobs:
        job.wait()
