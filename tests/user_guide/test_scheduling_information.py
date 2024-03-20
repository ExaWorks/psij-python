from psij import Job, JobSpec, JobAttributes
# from psij import JobAttributes
from executor_test_params import ExecutorTestParams

from _test_tools import assert_completed, _get_executor_instance


def test_user_guide_scheduling_info(execparams: ExecutorTestParams) -> None:

    job = Job(
        JobSpec(
            executable="/bin/date",
            attributes=JobAttributes(
                queue_name=execparams.queue_name,
                account=execparams.account
            )
        )
    )

    executor = _get_executor_instance(execparams, job)

    executor.submit(job)
    status = job.wait()
    assert_completed(job, status)
