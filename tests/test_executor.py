import uuid
from pathlib import Path

from psij import SubmitException, Job, JobSpec, JobState
from tempfile import TemporaryDirectory

from executor_test_params import ExecutorTestParams
from _test_tools import _get_executor_instance, _get_timeout, assert_completed, _make_test_dir


def test_simple_job(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/date', launcher=execparams.launcher))
    ex = _get_executor_instance(execparams, job)
    ex.submit(job)
    status = job.wait(timeout=_get_timeout(execparams))
    assert_completed(job, status)


def test_simple_job_redirect(execparams: ExecutorTestParams) -> None:
    _make_test_dir()
    with TemporaryDirectory(dir=Path.home() / '.psij' / 'test') as td:
        outp = Path(td, 'stdout.txt')
        job = Job(JobSpec(executable='/bin/echo', arguments=['-n', '_x_'], stdout_path=outp))
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert_completed(job, status)
        f = outp.open("r")
        contents = f.read()
        f.close()
        assert contents == '_x_'


def test_attach(execparams: ExecutorTestParams) -> None:
    job1 = Job(JobSpec(executable='/bin/sleep', arguments=['1']))
    ex = _get_executor_instance(execparams, job1)
    ex.submit(job1)
    job1.wait(target_states=[JobState.ACTIVE, JobState.COMPLETED])
    native_id = job1.native_id

    assert native_id is not None
    job2 = Job()
    ex.attach(job2, native_id)
    status2 = job2.wait(timeout=_get_timeout(execparams))
    assert_completed(job2, status2)
    status1 = job1.wait(timeout=_get_timeout(execparams))
    assert_completed(job1, status1)


def test_attach2(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/sleep', arguments=['1']))
    ex = _get_executor_instance(execparams, job)
    ex.submit(job)
    job.wait(target_states=[JobState.ACTIVE, JobState.COMPLETED])
    native_id = job.native_id

    assert native_id is not None
    job2 = Job()
    ex2 = _get_executor_instance(execparams)
    ex2.attach(job2, native_id)
    status = job2.wait(timeout=_get_timeout(execparams))
    assert_completed(job2, status)


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
        if status.exit_code is not None:
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
    assert_completed(job1, status1)
    assert_completed(job2, status2)


def test_env_var(execparams: ExecutorTestParams) -> None:
    _make_test_dir()
    with TemporaryDirectory(dir=Path.home() / '.psij' / 'test') as td:
        outp = Path(td, 'stdout.txt')
        job = Job(JobSpec(executable='/bin/bash', arguments=['-c', 'echo -n $TEST_VAR'],
                          stdout_path=outp))
        assert job.spec is not None
        job.spec.environment = {'TEST_VAR': '_y_'}
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert_completed(job, status)
        f = outp.open("r")
        contents = f.read()
        f.close()
        assert contents == '_y_'


def test_stdin_redirect(execparams: ExecutorTestParams) -> None:
    _make_test_dir()
    with TemporaryDirectory(dir=Path.home() / '.psij' / 'test') as td:
        inp = Path(td, 'stdin.txt')
        outp = Path(td, 'stdout.txt')

        rnd_str = uuid.uuid4().hex

        with open(inp, 'w') as inf:
            inf.write(rnd_str)

        job = Job(JobSpec(executable='/bin/cat', stdin_path=inp, stdout_path=outp))
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert_completed(job, status)

        with open(outp, 'r') as outf:
            contents = outf.read()

        assert contents == rnd_str


def test_list(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/sleep', arguments=['4']))
    ex = _get_executor_instance(execparams, job)
    ex.submit(job)
    assert job.native_id is not None
    ids = ex.list()
    assert job.native_id in ids
