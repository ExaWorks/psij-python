from psij import Job, JobSpec, JobExecutor, JobAttributes
# from psij import JobAttributes
from executor_test_params import ExecutorTestParams

from _test_tools import assert_completed


def test_user_guide_scheduling_info(execparams: ExecutorTestParams) -> None:
    executor = JobExecutor.get_instance(execparams.executor)

    job = Job(
        JobSpec(
            executable="/bin/date",
            attributes=JobAttributes(
                queue_name=execparams.queue_name,
                project_name=execparams.project_name
            )
        )
    )

    executor.submit(job)
    status = job.wait()
    assert_completed(job, status)
