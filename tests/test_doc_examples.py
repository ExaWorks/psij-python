"""
This file contains tests for PSI/J which can also be used as examples.

Since they are actively tested against, they are certain to be
up-to-date and to work as intended.
"""
import threading
import time
import pathlib
import typing
import tempfile
import socket
from datetime import timedelta

import psij


def _make_basic_job() -> psij.Job:
    """Helper function to create and return a `sleep 0` Job."""
    job = psij.Job()
    spec = psij.JobSpec()
    spec.executable = "/bin/sleep"
    spec.arguments = ["0"]
    job.spec = spec
    return job


def test_submit_and_wait_for_n_jobs() -> None:
    """Submit a number of `sleep 0` jobs and wait for them to complete."""
    jex = psij.JobExecutor.get_instance("local")
    num_jobs = 5
    jobs_list = []
    # create a list of `sleep 0` jobs and submit them
    for i in range(num_jobs):
        job = _make_basic_job()
        jobs_list.append(job)
        jex.submit(job)
    # wait for every job in the list to complete
    for job in jobs_list:
        job.wait(timedelta(seconds=3))  # waiting for 3 sec should be plenty


def test_run_n_throttle_m() -> None:
    """Run a number of `sleep 0` jobs with a set concurrency."""

    class ThrottledSubmitter:
        """Run a number of `sleep 0` jobs with a set concurrency.

        Only a certain number of jobs are allowed to be submitted at
        a time. The total number of jobs submitted is given
        by the `total_jobs` argument and the number of jobs that can
        be in flight at once is given by the `max_active_jobs` argument.
        """

        def __init__(self, total_jobs: int, max_active_jobs: int) -> None:
            self.jex = psij.JobExecutor.get_instance("local", ">= 0.0.1")
            # set callback to keep track of completed jobs
            self.jex.set_job_status_callback(self.callback)
            self.jobs: typing.List[psij.Job] = []
            self.current_job_index = 0
            self.total_jobs = total_jobs
            self.max_active_jobs = max_active_jobs
            self.lock = threading.RLock()
            if total_jobs < 1 or max_active_jobs < 1:
                raise ValueError("total_jobs and max_active_jobs must be > 0")

        def submit_next(self) -> None:
            """Submit the next job in the queue."""
            with self.lock:
                if self.current_job_index < self.total_jobs:
                    self.jex.submit(self.jobs[self.current_job_index])
                    self.current_job_index += 1

        def start(self) -> None:
            """Begin submission of jobs."""
            self.jobs.extend(_make_basic_job() for i in range(self.total_jobs))
            while self.current_job_index < self.max_active_jobs:
                self.submit_next()

        def callback(self, job: psij.Job, status: psij.JobStatus) -> None:
            """Check if a job has completed, and if so submit a new job."""
            if status.final:
                self.submit_next()

        def wait_all(self, check: bool = False) -> None:
            """Wait for all jobs to complete."""
            index = 0
            while index < self.total_jobs:
                if index < self.current_job_index:
                    # waiting for 3 seconds should be plenty
                    status = self.jobs[index].wait(timedelta(seconds=3))
                    if status is None:
                        raise RuntimeError("Job did not complete")
                    if check and status.exit_code != 0:
                        raise RuntimeError(f"Job failed with status {status}")
                    index += 1
                else:
                    time.sleep(0)

    # create an instance to submit 10 jobs, 3 at a time
    t = ThrottledSubmitter(10, 3)
    t.start()
    # check that all the jobs run successfully
    t.wait_all(check=True)


def test_job_parameters() -> None:
    """Submit a job with a custom environment and stdout path."""
    with tempfile.TemporaryDirectory() as td:
        output_path = pathlib.Path(td, "stdout.txt")
        # create a job that will print the hostname of the current machine
        # to the `output_path` file.
        job = psij.Job(
            psij.JobSpec(
                executable="/bin/hostname",
                stdout_path=output_path,
                environment={"FOOBAR": "BAZ", "BUZ": 1},  # custom environment has no effect here
                directory=pathlib.Path(td),  # CWD has no effect on result here
            )
        )
        ex = psij.JobExecutor.get_instance("local", ">= 0.0.1")
        ex.submit(job)
        status = job.wait(timedelta(seconds=3))  # 3 sec should be plenty in this case
        if status is None:
            raise RuntimeError("Job did not complete")
        if status.exit_code != 0:
            raise RuntimeError(f"Job failed with status {status}")
        with output_path.open("r") as fd:
            assert socket.gethostname() in fd.read()
