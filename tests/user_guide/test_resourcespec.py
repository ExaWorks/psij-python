from psij import Job, JobSpec, JobExecutor, ResourceSpecV1
from executor_test_params import ExecutorTestParams

from _test_tools import assert_completed


def test_user_guide_resourcespec(execparams: ExecutorTestParams) -> None:
    ex = JobExecutor.get_instance(execparams.executor)
    job = Job(
        JobSpec(
            executable='/bin/date',
            resources=ResourceSpecV1(
                node_count=2,
                processes_per_node=4
            )
        )
    )
    ex.submit(job)
    status = job.wait()
    assert_completed(job, status)
