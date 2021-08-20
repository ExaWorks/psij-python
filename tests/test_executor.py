from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from psij import SubmitException, Job, JobExecutor, JobSpec, JobState, JobStatus, JobExecutorConfig
from psij.executors.slurm import SlurmExecutorConfig


def assert_completed(job: Job) -> None:
    if job.status.state == JobState.FAILED:
        raise RuntimeError('Job (native_id: {}) failed: {}'.format(job.native_id,
                                                                   job.status.message))
    elif job.status.state == JobState.COMPLETED:
        return
    else:
        raise RuntimeError('Unexpected job state: {}'.format(job.status.state))


def get_config(executor: str) -> Optional[JobExecutorConfig]:
    if executor == 'slurm':
        return SlurmExecutorConfig()
    else:
        return None


def test_simple_job(executor: str) -> None:
    job = Job(JobSpec(executable='/bin/date'))
    exec = JobExecutor.get_instance(executor, config=get_config(executor))
    exec.submit(job)
    job.wait()
    assert_completed(job)


def test_simple_job_redirect(executor: str) -> None:
    with TemporaryDirectory() as td:
        outp = Path(td, 'stdout.txt')
        job = Job(JobSpec(executable='/bin/echo', arguments=['-n', '_x_'], stdout_path=outp))
        exec = JobExecutor.get_instance(executor, config=get_config(executor))
        exec.submit(job)
        job.wait()
        assert_completed(job)
        f = outp.open("r")
        contents = f.read()
        assert contents == '_x_'


def test_attach(executor: str) -> None:
    job = Job(JobSpec(executable='/bin/sleep', arguments=['1']))
    exec = JobExecutor.get_instance(executor, config=get_config(executor))
    exec.submit(job)
    job.wait(target_states=[JobState.ACTIVE, JobState.COMPLETED])
    native_id = job.native_id

    assert native_id is not None
    job2 = Job()
    exec.attach(job2, native_id)
    job2.wait()
    assert_completed(job2)


def test_cancel(executor: str) -> None:
    job = Job(JobSpec(executable='/bin/sleep', arguments=['1']))
    exec = JobExecutor.get_instance(executor, config=get_config(executor))
    exec.submit(job)
    job.wait(target_states=[JobState.ACTIVE])
    job.cancel()
    status = job.wait()
    assert status is not None
    assert status.state == JobState.CANCELED


def test_failing_job(executor: str) -> None:
    job = Job(JobSpec(executable='/bin/false'))
    exec = JobExecutor.get_instance(executor, config=get_config(executor))
    exec.submit(job)
    status = job.wait()
    assert status is not None
    assert status.state == JobState.FAILED
    assert status.exit_code is not None
    assert status.exit_code != 0


def test_missing_executable(executor: str) -> None:
    job = Job(JobSpec(executable='/bin/no_such_file_or_directory'))
    exec = JobExecutor.get_instance(executor, config=get_config(executor))
    # we don't know if this will fail with an exception or JobState.FAILED, so handle both
    try:
        exec.submit(job)
        status = job.wait()
        assert status is not None
        assert status.state == JobState.FAILED
        assert status.exit_code is not None
        assert status.exit_code != 0
    except SubmitException:
        pass


def test_parallel_jobs(executor: str) -> None:
    spec = JobSpec(executable='/bin/sleep', arguments=['5'])
    job1 = Job(spec)
    job2 = Job(spec)
    exec = JobExecutor.get_instance(executor, config=get_config(executor))
    exec.submit(job1)
    exec.submit(job2)
    job1.wait()
    job2.wait()
    assert_completed(job1)
    assert_completed(job2)
