from psij import Job, JobSpec, ResourceSpecV1
from executor_test_params import ExecutorTestParams

from _test_tools import assert_completed, _get_executor_instance


def test_user_guide_resourcespec(execparams: ExecutorTestParams) -> None:
    job = Job(
        JobSpec(
            executable='/bin/date',
            resources=ResourceSpecV1(
                node_count=2,
                processes_per_node=4
            )
        )
    )
    ex = _get_executor_instance(execparams, job)
    ex.submit(job)
    status = job.wait()
    assert_completed(job, status)
