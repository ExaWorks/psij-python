from pathlib import Path
from tempfile import TemporaryDirectory

from psij import SubmitException, Job, JobExecutor, JobSpec, JobState


def test_simple_job() -> None:
    job = Job(JobSpec(executable='/bin/date'))
    exec = JobExecutor.get_instance('local')
    exec.submit(job)
    job.wait()


def test_simple_job_redirect() -> None:
    with TemporaryDirectory() as td:
        outp = Path(td, 'stdout.txt')
        job = Job(JobSpec(executable='/bin/echo', arguments=['-n', '_x_'], stdout_path=outp))
        exec = JobExecutor.get_instance('local')
        exec.submit(job)
        job.wait()
        f = outp.open("r")
        contents = f.read()
        assert contents == '_x_'


def test_attach() -> None:
    job = Job(JobSpec(executable='/bin/sleep', arguments=['1']))
    exec = JobExecutor.get_instance('local')
    exec.submit(job)
    job.wait(target_states=[JobState.ACTIVE])
    native_id = job.native_id

    assert native_id is not None
    job2 = Job()
    exec.attach(job2, native_id)
    job2.wait()


def test_cancel() -> None:
    job = Job(JobSpec(executable='/bin/sleep', arguments=['1']))
    exec = JobExecutor.get_instance('local')
    exec.submit(job)
    job.wait(target_states=[JobState.ACTIVE])
    job.cancel()
    status = job.wait()
    assert status is not None
    assert status.state == JobState.CANCELED


def test_failing_job() -> None:
    job = Job(JobSpec(executable='/bin/false'))
    exec = JobExecutor.get_instance('local')
    exec.submit(job)
    status = job.wait()
    assert status is not None
    assert status.state == JobState.FAILED
    assert status.exit_code is not None
    assert status.exit_code != 0


def test_missing_executable() -> None:
    job = Job(JobSpec(executable='/bin/no_such_file_or_directory'))
    exec = JobExecutor.get_instance('local')
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
