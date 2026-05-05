from executor_test_params import ExecutorTestParams

from _test_tools import assert_completed, _get_async_executor_instance


def test_getting_started_single_job(execparams: ExecutorTestParams) -> None:
    from psij import AsyncJob, JobSpec, AsyncJobExecutor

    async def run_job():
        job = AsyncJob(JobSpec(executable="/bin/date"))
        ex = _get_async_executor_instance(execparams, job)
        await ex.submit(job)

        status = await job.wait()
        assert_completed(job, status)
