import pytest

from typing import Optional
from pathlib import Path
from tempfile import TemporaryDirectory

from psij import SubmitException, Job, JobExecutor, JobSpec, JobState

tests = [['local', None],
         ['saga', 'fork://localhost/'],
         ['saga', 'ssh://localhost/']]


@pytest.mark.parametrize('name,url', tests)
def test_simple_job(name: str, url: Optional[str]) -> None:
    job = Job(JobSpec(executable='/bin/date'))
    jex = JobExecutor.get_instance(name=name, url=url)
    jex.submit(job)
    job.wait()


@pytest.mark.parametrize('name,url', tests)
def test_simple_job_redirect(name: str, url: Optional[str]) -> None:
    with TemporaryDirectory() as td:
        outp = Path(td, 'stdout.txt')
        job = Job(JobSpec(executable='/bin/echo', arguments=['-n', '_x_'],
                          stdout_path=outp))
        jex = JobExecutor.get_instance(name=name, url=url)
        jex.submit(job)
        job.wait()
        f = outp.open("r")
        contents = f.read()
        assert contents == '_x_'


@pytest.mark.parametrize('name,url', tests)
def test_attach(name: str, url: Optional[str]) -> None:
    job = Job(JobSpec(executable='/bin/sleep', arguments=['1']))
    jex = JobExecutor.get_instance(name=name, url=url)
    jex.submit(job)
    job.wait(target_states=[JobState.ACTIVE])
    native_id = job.native_id

    assert native_id is not None
    job2 = Job()
    jex.attach(job2, native_id)
    job2.wait()


@pytest.mark.parametrize('name,url', tests)
def test_cancel(name: str, url: Optional[str]) -> None:
    job = Job(JobSpec(executable='/bin/sleep', arguments=['1']))
    jex = JobExecutor.get_instance(name=name, url=url)
    jex.submit(job)
    job.wait(target_states=[JobState.ACTIVE])
    job.cancel()
    status = job.wait()
    assert status is not None
    assert status.state == JobState.CANCELED


@pytest.mark.parametrize('name,url', tests)
def test_failing_job(name: str, url: Optional[str]) -> None:
    job = Job(JobSpec(executable='/bin/false'))
    jex = JobExecutor.get_instance(name=name, url=url)
    jex.submit(job)
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
