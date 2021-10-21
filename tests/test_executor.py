import pytest

from typing import Optional
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from psij import SubmitException, Job, JobExecutor, JobSpec, JobState, JobStatus, JobExecutorConfig
from psij.executors.slurm import SlurmExecutorConfig
from executor_test_params import ExecutorTestParams


def assert_completed(job: Job) -> None:
    if job.status.state == JobState.FAILED:
        raise RuntimeError('Job (native_id: {}) failed: {}'.format(job.native_id,
                                                                   job.status.message))
    elif job.status.state == JobState.COMPLETED:
        return
    else:
        raise RuntimeError('Unexpected job state: {}'.format(job.status.state))

from psij import SubmitException, Job, JobExecutor, JobSpec, JobState


def _get_executor_instance(ep: ExecutorTestParams, job: Job) -> JobExecutor:
    job.spec.launcher = ep.launcher
    return JobExecutor.get_instance(ep.executor, url=ep.url)


def test_simple_job(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/date', launcher=execparams.launcher))
    exec = _get_executor_instance(execparams, job)
    exec.submit(job)
    job.wait()


def test_simple_job_redirect(execparams: ExecutorTestParams) -> None:
    with TemporaryDirectory(dir=Path.home() / '.psij' / 'work') as td:
        outp = Path(td, 'stdout.txt')
        job = Job(JobSpec(executable='/bin/echo', arguments=['-n', '_x_'], stdout_path=outp))
        exec = _get_executor_instance(execparams, job)
        exec.submit(job)
        job.wait()
        f = outp.open("r")
        contents = f.read()
        assert contents == '_x_'


def test_attach(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/sleep', arguments=['1']))
    exec = _get_executor_instance(execparams, job)
    exec.submit(job)
    job.wait(target_states=[JobState.ACTIVE, JobState.COMPLETED])
    native_id = job.native_id

    assert native_id is not None
    job2 = Job()
    exec.attach(job2, native_id)
    job2.wait()


def test_cancel(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/sleep', arguments=['60']))
    exec = _get_executor_instance(execparams, job)
    exec.submit(job)
    job.wait(target_states=[JobState.ACTIVE])
    job.cancel()
    status = job.wait()
    assert status is not None
    assert status.state == JobState.CANCELED


def test_failing_job(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/false'))
    exec = _get_executor_instance(execparams, job)
    exec.submit(job)
    status = job.wait()
    assert status is not None
    assert status.state == JobState.FAILED
    assert status.exit_code is not None
    assert status.exit_code != 0


@pytest.mark.parametrize('name,url', tests)
def test_missing_executable(name: str, url: Optional[str]) -> None:
    job = Job(JobSpec(executable='/bin/no_such_file_or_directory'))
    jex = JobExecutor.get_instance(name=name, url=url)
    # we don't know if this will fail with an exception or JobState.FAILED,
    # so handle both
    try:
        jex.submit(job)
        status = job.wait()
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
    exec = _get_executor_instance(execparams, job1)
    exec.submit(job1)
    exec.submit(job2)
    job1.wait()
    job2.wait()
    assert_completed(job1)
    assert_completed(job2)
