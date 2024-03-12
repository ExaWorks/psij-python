from pathlib import Path

from executor_test_params import ExecutorTestParams
from _test_tools import _get_executor_instance, _get_timeout, assert_completed, _tempfile, \
    _temppath, _tempdir, _write_file, _read_file
from psij import Job, JobSpec, JobState
from psij.staging import StageIn, StageOut, StagingMode, StageOutFlags
import pytest


@pytest.mark.parametrize('mode', [StagingMode.COPY, StagingMode.MOVE, StagingMode.LINK])
def test_stagein(execparams: ExecutorTestParams, mode: StagingMode) -> None:
    if execparams.executor != 'local' and execparams.launcher != 'single':
        # The launcher should not affect the staging, so we test all launchers locally,
        # but for the other executors, we only test with the single launcher
        pytest.skip()
    # The executors are not mandated to implement the staging modes, but they are
    # meant to default to COPY if MOVE and LINK are not implemented, so we test
    # that things function correctly, but not how that is done
    with _temppath() as out_path, _temppath() as err_path, _tempdir() as dir:
        with _tempfile() as f1, _tempfile() as f2:
            _write_file(f1, 'ABCD')
            _write_file(f2, 'EFGH')

            job = Job(JobSpec('/bin/cat', ['in1.txt', 'subdir/in2.txt'],
                              directory=dir, stdout_path=out_path, stderr_path=err_path,
                              launcher=execparams.launcher))
            assert job.spec is not None
            job.spec.stage_in = {
                StageIn(f1.name, 'in1.txt', mode=mode),
                StageIn(f2.name, 'subdir/in2.txt', mode=mode),
            }
            ex = _get_executor_instance(execparams, job)
            ex.submit(job)
            status = job.wait(timeout=_get_timeout(execparams))
            assert_completed(job, status)

            assert _read_file(out_path) == 'ABCDEFGH'


@pytest.mark.parametrize('mode', [StagingMode.COPY, StagingMode.MOVE, StagingMode.LINK])
def test_dir_stagein(execparams: ExecutorTestParams, mode: StagingMode) -> None:
    if execparams.executor != 'local' and execparams.launcher != 'single':
        pytest.skip()
    # The executors are not mandated to implement the staging modes, but they are
    # meant to default to COPY if MOVE and LINK are not implemented, so we test
    # that things function correctly, but not how that is done
    with _temppath() as out_path, _temppath() as err_path, _tempdir() as dir:
        with _tempdir() as in_dir:
            sub_dir = in_dir / 'subdir'
            sub_dir.mkdir()
            f1 = sub_dir / 'in3.txt'
            f2 = sub_dir / 'in4.txt'
            _write_file(f1, 'IJKL')
            _write_file(f2, 'MNOP')

            job = Job(JobSpec('/bin/cat', ['indir/in3.txt', 'indir/in4.txt'],
                              directory=dir, stdout_path=out_path, stderr_path=err_path,
                              launcher=execparams.launcher))
            assert job.spec is not None
            job.spec.stage_in = {
                StageIn(sub_dir, 'indir', mode=mode),
            }
            ex = _get_executor_instance(execparams, job)
            ex.submit(job)
            status = job.wait(timeout=_get_timeout(execparams))
            assert_completed(job, status)

            assert _read_file(out_path) == 'IJKLMNOP'


@pytest.mark.parametrize('mode', [StagingMode.COPY, StagingMode.MOVE, StagingMode.LINK])
def test_stageout(execparams: ExecutorTestParams, mode: StagingMode) -> None:
    if execparams.executor != 'local' and execparams.launcher != 'single':
        pytest.skip()
    with _temppath() as out_path, _temppath() as err_path, _tempdir() as dir:
        job = Job(JobSpec('/bin/echo', ['-n', 'CDEF'], directory=dir,
                          stdout_path='out.txt', stderr_path=err_path,
                          launcher=execparams.launcher))
        assert job.spec is not None
        job.spec.stage_out = {
            StageOut('out.txt', out_path, mode=mode)
        }
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert_completed(job, status)

        assert _read_file(out_path) == 'CDEF'


def test_stageout_flags1(execparams: ExecutorTestParams) -> None:
    if execparams.executor != 'local' and execparams.launcher != 'single':
        pytest.skip()
    with _temppath() as out1_path, _temppath() as out2_path, _temppath() as err_path, \
            _tempdir() as dir:

        out2_path.unlink()
        job = Job(JobSpec('/bin/echo', ['-n', 'ABC123'],
                          directory=dir, stdout_path='out1.txt', stderr_path=err_path,
                          launcher=execparams.launcher))
        assert job.spec is not None
        job.spec.stage_out = {
            StageOut('out1.txt', out1_path, flags=StageOutFlags.IF_PRESENT),
            StageOut('out2.txt', out2_path, flags=StageOutFlags.IF_PRESENT)
        }
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert_completed(job, status)

        assert _read_file(out1_path) == 'ABC123'
        assert not out2_path.exists()


def test_stageout_flags2(execparams: ExecutorTestParams) -> None:
    if execparams.executor != 'local' and execparams.launcher != 'single':
        pytest.skip()
    with _temppath() as out_path, _temppath() as err_path, _tempdir() as dir:
        job = Job(JobSpec('/bin/echo', ['-n', 'EFG456'],
                          directory=dir, stdout_path='out.txt', stderr_path=err_path,
                          launcher=execparams.launcher))
        assert job.spec is not None
        job.spec.stage_out = {
            StageOut('out.txt', out_path, flags=StageOutFlags.ON_SUCCESS),
        }
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert_completed(job, status)

        assert _read_file(out_path) == 'EFG456'

    with _temppath() as out_path, _temppath() as err_path, _tempdir() as dir:
        out_path.unlink()
        job = Job(JobSpec('/bin/bash', ['-c', 'echo -n "ABC" > out.txt; exit 1'],
                          directory=dir, stderr_path=err_path,
                          launcher=execparams.launcher))
        assert job.spec is not None
        job.spec.stage_out = {
            StageOut('out.txt', out_path, flags=StageOutFlags.ON_SUCCESS),
        }
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert status
        assert status.state == JobState.FAILED
        assert not out_path.exists()


def test_stageout_flags3(execparams: ExecutorTestParams) -> None:
    if execparams.executor != 'local' and execparams.launcher != 'single':
        pytest.skip()
    with _temppath() as out_path, _temppath() as err_path, _tempdir() as dir:
        out_path.unlink()
        job = Job(JobSpec('/bin/echo', ['-n', 'EFG456'],
                          directory=dir, stdout_path='out.txt', stderr_path=err_path,
                          launcher=execparams.launcher))
        assert job.spec is not None
        job.spec.stage_out = {
            StageOut('out.txt', out_path, flags=StageOutFlags.ON_ERROR),
        }
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert_completed(job, status)

        assert not out_path.exists()

    with _temppath() as out_path, _temppath() as err_path, _tempdir() as dir:
        job = Job(JobSpec('/bin/bash', ['-c', 'echo -n "ABC" > out.txt; exit 1'],
                          directory=dir, stderr_path=err_path,
                          launcher=execparams.launcher))
        assert job.spec is not None
        job.spec.stage_out = {
            StageOut('out.txt', out_path, flags=StageOutFlags.ON_ERROR),
        }
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert status
        assert status.state == JobState.FAILED
        assert out_path.exists()
        assert _read_file(out_path) == 'ABC'


def test_cleanup(execparams: ExecutorTestParams) -> None:
    if execparams.executor != 'local' and execparams.launcher != 'single':
        pytest.skip()
    with _temppath() as out_path, _temppath() as err_path, _tempdir() as dir:
        job = Job(JobSpec('/bin/echo', ['-n', 'ABC'],
                          directory=dir, stdout_path='out.txt', stderr_path=err_path,
                          launcher=execparams.launcher))
        assert job.spec is not None
        job.spec.stage_out = {
            StageOut('out.txt', out_path, flags=StageOutFlags.IF_PRESENT),
        }
        job.spec.cleanup = {Path('out.txt')}
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert_completed(job, status)
        assert out_path.exists()
        assert not (dir / 'out.txt').exists()
        assert _read_file(out_path) == 'ABC'


def test_cleanup2(execparams: ExecutorTestParams) -> None:
    if execparams.executor != 'local' and execparams.launcher != 'single':
        pytest.skip()
    with _temppath() as out_path, _temppath() as err_path, _tempdir() as dir:
        job = Job(JobSpec('/bin/bash', ['-c', 'echo -n "ABC" > out.txt; exit 1'],
                          directory=dir, stderr_path=err_path,
                          launcher=execparams.launcher))
        assert job.spec is not None
        job.spec.stage_out = {
            StageOut('out.txt', out_path, flags=StageOutFlags.IF_PRESENT),
        }
        job.spec.cleanup = {Path('out.txt')}
        job.spec.cleanup_flags = StageOutFlags.ON_SUCCESS
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert status is not None
        assert status.state == JobState.FAILED
        assert (dir / 'out.txt').exists()
        assert _read_file(out_path) == 'ABC'
