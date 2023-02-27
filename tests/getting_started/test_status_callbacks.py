import time
from psij import Job, JobSpec, JobStatus, JobExecutor
from executor_test_params import ExecutorTestParams

count = 10


def test_getting_started_scheduling_info(execparams: ExecutorTestParams) -> None:
    def callback(job: Job, status: JobStatus) -> None:
        global count

        if status.final:
            print(f"Job {job} completed with status {status}")
            count -= 1

    ex = JobExecutor.get_instance(execparams.executor)
    ex.set_job_status_callback(callback)

    for _ in range(count):
        job = Job(JobSpec(executable="/bin/date"))
        ex.submit(job)

    while count > 0:
        time.sleep(0.01)
