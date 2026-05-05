import asyncio

from psij import JobSpec, AsyncJobExecutor, AsyncJob
from _test_tools import assert_completed


# DOC: start
async def run_job_async() -> None:
    ex = AsyncJobExecutor.get_instance('local')
    job = AsyncJob(JobSpec(executable='/bin/date'))
    await ex.submit(job)
    status = await job.wait()
    assert_completed(job, status)  # DOC: skip
# DOC: end


def test_user_guide_plain_job() -> None:
    asyncio.run(run_job_async())
