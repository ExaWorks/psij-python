from datetime import timedelta
from pathlib import Path
from typing import Optional

from psij import SubmitException, Job, JobExecutor, JobSpec, JobState, JobAttributes, JobStatus
from psij.executors.batch.batch_scheduler_executor import BatchSchedulerExecutorConfig
from tempfile import TemporaryDirectory

from executor_test_params import ExecutorTestParams

import logging

logger = logging.getLogger(__name__)

_QUICK_EXECUTORS = set(['local', 'batch-test', 'saga'])


def _get_timeout(execparams: ExecutorTestParams) -> Optional[timedelta]:
    if execparams.executor in _QUICK_EXECUTORS:
        return timedelta(minutes=10)
    else:
        return None


def assert_completed(status: Optional[JobStatus]) -> None:
    assert status is not None
    assert status.state == JobState.COMPLETED


def _get_executor_instance(ep: ExecutorTestParams, job: Job) -> JobExecutor:
    assert job.spec is not None
    job.spec.launcher = ep.launcher
    job.spec.attributes = JobAttributes(custom_attributes=ep.custom_attributes)
    # BENC: how does this work with parameterisation by name in tests? keep_files is only a parameter for *some* executors...
    # most immediately i care about this for tests, but on a deeper level, how does it affect things when I'm running inside some other code and talking about executors by name rather than by python construction? (i.e. pytest as a "sample application doing normal sample application things". the parsl story is clear here: construct using Python, don't try to build your own config language on top. but i don't think that's whats happening in psij (c.f. mini language for specifying both executor and launcher)
    # TODO: write an issue about that
    job_executor_config = BatchSchedulerExecutorConfig(keep_files=True)
    return JobExecutor.get_instance(ep.executor, url=ep.url, config=job_executor_config)


def test_simple_job(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/date', launcher=execparams.launcher))
    ex = _get_executor_instance(execparams, job)
    ex.submit(job)
    status = job.wait(timeout=_get_timeout(execparams))
    assert_completed(status)


def test_simple_job_redirect(execparams: ExecutorTestParams) -> None:
    with TemporaryDirectory(dir=Path.home() / '.psij' / 'work') as td:
        logger.warn("BENC: entering temporary dir")
        outp = Path(td, 'stdout.txt')
        job = Job(JobSpec(executable='/bin/echo', arguments=['-n', '_x_'], stdout_path=outp))
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        logger.warn("BENC: starting wait")
        status = job.wait(timeout=_get_timeout(execparams))
        logger.warn("BENC: ending wait")
        assert_completed(status)
        f = outp.open("r")
        contents = f.read()
        f.close()
        assert contents == '_x_'
        logger.warn("BENC: exited temporary dir")


def test_attach(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/sleep', arguments=['1']))
    ex = _get_executor_instance(execparams, job)
    ex.submit(job)
    job.wait(target_states=[JobState.ACTIVE, JobState.COMPLETED])
    native_id = job.native_id

    assert native_id is not None
    job2 = Job()
    ex.attach(job2, native_id)
    status = job2.wait(timeout=_get_timeout(execparams))
    assert_completed(status)


def test_cancel(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/sleep', arguments=['60']))
    ex = _get_executor_instance(execparams, job)
    ex.submit(job)
    job.wait(target_states=[JobState.ACTIVE])
    job.cancel()
    status = job.wait(timeout=_get_timeout(execparams))
    assert status is not None
    assert status.state == JobState.CANCELED


def test_failing_job(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/false'))
    ex = _get_executor_instance(execparams, job)
    ex.submit(job)
    status = job.wait(timeout=_get_timeout(execparams))
    assert status is not None
    assert status.state == JobState.FAILED
    assert status.exit_code is not None
    assert status.exit_code != 0


def test_missing_executable(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/no_such_file_or_directory'))
    ex = _get_executor_instance(execparams, job)
    # we don't know if this will fail with an exception or JobState.FAILED,
    # so handle both
    try:
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert status is not None
        assert status.state == JobState.FAILED
        assert status.exit_code is not None
        assert status.exit_code != 0
    except SubmitException:
        pass


def test_parallel_jobs(execparams: ExecutorTestParams) -> None:
    spec = JobSpec(executable='/bin/sleep', arguments=['5'])
    job1 = Job(spec)
    job2 = Job(spec)
    ex = _get_executor_instance(execparams, job1)
    ex.submit(job1)
    ex.submit(job2)
    status1 = job1.wait(timeout=_get_timeout(execparams))
    status2 = job2.wait(timeout=_get_timeout(execparams))
    assert_completed(status1)
    assert_completed(status2)
