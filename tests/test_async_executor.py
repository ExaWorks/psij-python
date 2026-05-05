from pathlib import Path
from typing import List

import pytest

from psij import SubmitException, JobSpec, JobState, AsyncJob, JobStatus, AsyncJobExecutor, Job
from tempfile import TemporaryDirectory

from executor_test_params import ExecutorTestParams
from _test_tools import _get_timeout, assert_completed, _make_test_dir, \
    _get_async_executor_instance, _get_executor_instance
from psij._async import AsyncExecutorWrapper, SyncExecutorWrapper

pytest_plugins = ('pytest_asyncio',)


@pytest.mark.asyncio
async def test_async_simple_job(execparams: ExecutorTestParams) -> None:
    job = AsyncJob(JobSpec(executable='/bin/date', launcher=execparams.launcher))
    ex = _get_async_executor_instance(execparams, job)
    await ex.submit(job)
    status = await job.wait(timeout=_get_timeout(execparams))
    assert_completed(job, status)


@pytest.mark.asyncio
async def test_async_simple_job_redirect(execparams: ExecutorTestParams) -> None:
    _make_test_dir()
    with TemporaryDirectory(dir=Path.home() / '.psij' / 'test') as td:
        outp = Path(td, 'stdout.txt')
        job = AsyncJob(JobSpec(executable='/bin/echo', arguments=['-n', '_x_'], stdout_path=outp))
        ex = _get_async_executor_instance(execparams, job)
        await ex.submit(job)
        status = await job.wait(timeout=_get_timeout(execparams))
        assert_completed(job, status)
        f = outp.open("r")
        contents = f.read()
        f.close()
        assert contents == '_x_'


@pytest.mark.asyncio
async def test_async_stderr_redirect(execparams: ExecutorTestParams) -> None:
    _make_test_dir()
    with TemporaryDirectory(dir=Path.home() / '.psij' / 'test') as td:
        outp = Path(td, 'stderr.txt')
        job = AsyncJob(JobSpec(executable='/bin/bash', arguments=['-c', 'echo -n _x_ 1>&2'],
                               stderr_path=outp))
        ex = _get_async_executor_instance(execparams, job)
        await ex.submit(job)
        status = await job.wait(timeout=_get_timeout(execparams))
        assert_completed(job, status)
        f = outp.open("r")
        contents = f.read()
        f.close()
        assert contents == '_x_'


@pytest.mark.asyncio
async def test_async_attach(execparams: ExecutorTestParams) -> None:
    job1 = AsyncJob(JobSpec(executable='/bin/sleep', arguments=['1']))
    ex = _get_async_executor_instance(execparams, job1)
    await ex.submit(job1)
    await job1.wait(target_states=[JobState.ACTIVE, JobState.COMPLETED])
    native_id = job1.native_id

    assert native_id is not None
    job2 = AsyncJob()
    await ex.attach(job2, native_id)
    status2 = await job2.wait(timeout=_get_timeout(execparams))
    assert_completed(job2, status2, attached=True)
    status1 = await job1.wait(timeout=_get_timeout(execparams))
    assert_completed(job1, status1)


@pytest.mark.asyncio
async def test_async_attach2(execparams: ExecutorTestParams) -> None:
    job = AsyncJob(JobSpec(executable='/bin/sleep', arguments=['1']))
    ex = _get_async_executor_instance(execparams, job)
    await ex.submit(job)
    await job.wait(target_states=[JobState.ACTIVE, JobState.COMPLETED])
    native_id = job.native_id

    assert native_id is not None
    job2 = AsyncJob()
    ex2 = _get_async_executor_instance(execparams)
    await ex2.attach(job2, native_id)
    status = await job2.wait(timeout=_get_timeout(execparams))
    assert_completed(job2, status, attached=True)


@pytest.mark.asyncio
async def test_async_cancel(execparams: ExecutorTestParams) -> None:
    job = AsyncJob(JobSpec(executable='/bin/sleep', arguments=['60']))
    ex = _get_async_executor_instance(execparams, job)
    await ex.submit(job)
    await job.wait(target_states=[JobState.ACTIVE])
    await job.cancel()
    status = await job.wait(timeout=_get_timeout(execparams))
    assert status is not None
    assert status.state == JobState.CANCELED


@pytest.mark.asyncio
async def test_async_failing_job(execparams: ExecutorTestParams) -> None:
    job = AsyncJob(JobSpec(executable='/bin/false'))
    ex = _get_async_executor_instance(execparams, job)
    await ex.submit(job)
    status = await job.wait(timeout=_get_timeout(execparams))
    assert status is not None
    assert status.state == JobState.FAILED
    assert status.exit_code is not None
    assert status.exit_code != 0


@pytest.mark.asyncio
async def test_async_missing_executable(execparams: ExecutorTestParams) -> None:
    job = AsyncJob(JobSpec(executable='/bin/no_such_file_or_directory'))
    ex = _get_async_executor_instance(execparams, job)
    # we don't know if this will fail with an exception or JobState.FAILED,
    # so handle both
    try:
        await ex.submit(job)
        status = await job.wait(timeout=_get_timeout(execparams))
        assert status is not None
        assert status.state == JobState.FAILED
        if status.exit_code is not None:
            assert status.exit_code != 0
    except SubmitException:
        pass


@pytest.mark.asyncio
async def test_async_parallel_jobs(execparams: ExecutorTestParams) -> None:
    spec = JobSpec(executable='/bin/sleep', arguments=['5'])
    job1 = AsyncJob(spec)
    job2 = AsyncJob(spec)
    ex = _get_async_executor_instance(execparams, job1)
    await ex.submit(job1)
    await ex.submit(job2)
    status1 = await job1.wait(timeout=_get_timeout(execparams))
    status2 = await job2.wait(timeout=_get_timeout(execparams))
    assert_completed(job1, status1)
    assert_completed(job2, status2)


@pytest.mark.asyncio
async def test_async_list(execparams: ExecutorTestParams) -> None:
    job = AsyncJob(JobSpec(executable='/bin/sleep', arguments=['4']))
    ex = _get_async_executor_instance(execparams, job)
    await ex.submit(job)
    assert job.native_id is not None
    ids = await ex.list()
    assert job.native_id in ids
    status = await job.wait(timeout=_get_timeout(execparams))
    assert_completed(job, status)


@pytest.mark.asyncio
async def test_async_callbacks1() -> None:
    cb_states: List[JobState] = []

    async def state_cb(job: AsyncJob, status: JobStatus) -> None:
        cb_states.append(status.state)

    job = AsyncJob(JobSpec(executable='/bin/false'))
    job.set_job_status_callback(state_cb)
    jex = AsyncJobExecutor.get_instance(name='local')
    await jex.submit(job)
    await job.wait()

    print('States: %s' % cb_states)

    assert len(cb_states) == 6
    assert cb_states[0] == JobState.QUEUED
    assert cb_states[1] == JobState.STAGE_IN
    assert cb_states[2] == JobState.ACTIVE
    assert cb_states[3] == JobState.STAGE_OUT
    assert cb_states[4] == JobState.CLEANUP
    assert cb_states[5] == JobState.FAILED

    cb_states = []
    job = AsyncJob(JobSpec(executable='/bin/date'))
    job.set_job_status_callback(state_cb)
    jex = AsyncJobExecutor.get_instance(name='local')
    await jex.submit(job)
    await job.wait()

    assert len(cb_states) == 6
    assert cb_states[0] == JobState.QUEUED
    assert cb_states[1] == JobState.STAGE_IN
    assert cb_states[2] == JobState.ACTIVE
    assert cb_states[3] == JobState.STAGE_OUT
    assert cb_states[4] == JobState.CLEANUP
    assert cb_states[5] == JobState.COMPLETED


@pytest.mark.asyncio
async def test_async_wrapper(execparams: ExecutorTestParams) -> None:
    job = AsyncJob(JobSpec(executable='/bin/date', launcher=execparams.launcher))
    ex0 = _get_executor_instance(execparams, job)
    ex = AsyncExecutorWrapper(ex0)
    await ex.submit(job)
    status = await job.wait(timeout=_get_timeout(execparams))
    assert_completed(job, status)


@pytest.mark.asyncio
async def test_sync_wrapper(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/date', launcher=execparams.launcher))
    ex0 = _get_async_executor_instance(execparams, job)
    ex = SyncExecutorWrapper(ex0)
    ex.submit(job)
    status = job.wait(timeout=_get_timeout(execparams))
    assert_completed(job, status)
