from psij import Job, JobSpec, JobExecutor, ResourceSpecV1, JobAttributes
from executor_test_params import ExecutorTestParams


def test_getting_started_scheduling_info(execparams: ExecutorTestParams) -> None:
    executor = JobExecutor.get_instance(execparams.executor)

    job = Job(
        JobSpec(
            executable="/bin/date",
            resources=ResourceSpecV1(node_count=1),
            # attributes=JobAttributes(
            #     queue_name="<QUEUE_NAME>", project_name="<ALLOCATION>"
            # ),
        )
    )

    executor.submit(job)
