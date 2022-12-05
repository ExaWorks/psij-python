import os
from time import sleep
from psij import Job, JobExecutor, JobSpec, JobAttributes

QUEUE_NAME = os.environ.get("LLNL_QUEUE_NAME")
status_callback_job_count = 3

def getting_started_basic_usage(compute_platform:str) -> None:
    ex = JobExecutor.get_instance(compute_platform)
    job = Job(
    JobSpec(
        executable="/bin/date", 
        attributes=JobAttributes(queue_name=QUEUE_NAME)
    )
    )
    ex.submit(job)

def getting_started_adding_complexity(compute_platform:str) -> None:
    num_jobs = 3
    ex = JobExecutor.get_instance(compute_platform)
    for _ in range(num_jobs):
        job = Job(
            JobSpec(
                    executable="/bin/date",
                    attributes=JobAttributes(queue_name=QUEUE_NAME)
            )
        )
        ex.submit(job)

def getting_started_status_callbacks(compute_platform:str) -> None:
    def callback(job, status):
        global status_callback_job_count

        if status.final:
            print(f"Job {job} completed with status {status}")
            status_callback_job_count -= 1

    ex = JobExecutor.get_instance(compute_platform)
    ex.set_job_status_callback(callback)

    for _ in range(status_callback_job_count):
        job = Job(
            JobSpec(
                    executable="/bin/date",
                    attributes=JobAttributes(queue_name=QUEUE_NAME)
            )
        )
        ex.submit(job)

    while status_callback_job_count > 0:
        sleep(0.01)

def our_test(compute_platform:str) -> None:
    jex = JobExecutor.get_instance(compute_platform)
    num_jobs = 3

    def make_job():
        job = Job()
        spec = JobSpec()
        spec.attributes.queue_name = QUEUE_NAME
        spec.executable = 'echo'
        spec.arguments = ['HELLO WORLD!']
        if compute_platform == "lsf":
            spec.attributes.set_custom_attribute("lsf.nnodes", num_jobs)
        job.spec = spec
        return job

    jobs = []
    for _ in range(num_jobs):
        job = make_job()
        jobs.append(job)
        jex.submit(job)

    for job in jobs:
        job.wait()


compute_env_slurm = "slurm"
compute_env_lsf = "lsf"

def test_getting_started_basic_usage_slurm():
    getting_started_basic_usage(compute_env_slurm)

def test_getting_started_adding_complexity_slurm():
    getting_started_adding_complexity(compute_env_slurm)

def test_getting_started_status_callback_slurm():
    getting_started_status_callbacks(compute_env_slurm)

def test_llnl_slurm():
    our_test(compute_env_slurm)

def test_getting_started_basic_usage_lsf():
    getting_started_basic_usage(compute_env_lsf)

def test_getting_started_adding_complexity_lsf():
    getting_started_adding_complexity(compute_env_lsf)

def test_getting_started_status_callback_lsf():
    getting_started_status_callbacks(compute_env_lsf)

def test_llnl_lsf():
    our_test(compute_env_lsf)