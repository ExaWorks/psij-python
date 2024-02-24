import os
import shutil
import tempfile
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Optional, Union, Iterator, IO

from executor_test_params import ExecutorTestParams

from psij import JobStatus, JobState, Job, JobExecutor, JobAttributes

_QUICK_EXECUTORS = set(['local', 'batch-test'])


def _make_test_dir() -> None:
    (Path.home() / '.psij' / 'test').mkdir(parents=True, exist_ok=True)


def _get_timeout(execparams: ExecutorTestParams) -> Optional[timedelta]:
    if execparams.executor in _QUICK_EXECUTORS:
        return timedelta(minutes=10)
    else:
        return None


def _read_file(path: Optional[Path]) -> str:
    if path is None:
        return ''

    with open(path, 'r') as f:
        return f.read()


def assert_completed(job: Job, status: Optional[JobStatus], attached: bool = False) -> None:
    assert status is not None
    if status.state != JobState.COMPLETED:
        if not attached:
            assert job.spec is not None
            try:
                stdout = _read_file(job.spec.stdout_path)
            except Exception:
                stdout = '<not found>'
            try:
                stderr = _read_file(job.spec.stderr_path)
            except Exception:
                stderr = '<not found>'
            raise AssertionError('Job not completed. Exit code: %s, Status message: %s, '
                                 'stdout: %s, stderr: %s'
                                 % (status.exit_code, status.message, stdout, stderr))
        else:
            raise AssertionError('Job not completed. Exit code: %s, Status message: %s'
                                 % (status.exit_code, status.message))


def _get_executor_instance(ep: ExecutorTestParams, job: Optional[Job] = None) -> JobExecutor:
    if job is not None:
        assert job.spec is not None
        job.spec.launcher = ep.launcher
        job.spec.attributes = JobAttributes(custom_attributes=ep.custom_attributes)
        if ep.project_name is not None:
            job.spec.attributes.project_name = ep.project_name
        if ep.queue_name is not None:
            job.spec.attributes.queue_name = ep.queue_name
    return JobExecutor.get_instance(ep.executor, url=ep.url)


@contextmanager
def _deploy(path: Union[Path, str]) -> Iterator[Path]:
    # Copies `path` to a directory assumed to be on a shared FS (~/.psij/test) and
    # returns the resulting path
    if isinstance(path, str):
        path = Path(path)
    with tempfile.NamedTemporaryFile(dir=Path.home() / '.psij' / 'test', delete=False) as df:
        try:
            df.close()
            shutil.copyfile(path, df.name)
            yield Path(df.name)
        finally:
            os.unlink(df.name)


@contextmanager
def _tempfile() -> Iterator[IO[str]]:
    # we have type: ignore above because mypy complains that _TemporaryFileWrapper is generic,
    # but adding [str] to it results in a runtime error stating that _TemporaryFileWrapper is
    # not subscriptable
    _make_test_dir()
    test_dir = Path.home() / '.psij' / 'test'
    with tempfile.NamedTemporaryFile(mode='w', dir=test_dir, delete=False) as f:
        try:
            yield f
        finally:
            try:
                os.unlink(f.name)
            except FileNotFoundError:
                # some tests may remove the file themselves
                pass


@contextmanager
def _temppath() -> Iterator[Path]:
    _make_test_dir()
    test_dir = Path.home() / '.psij' / 'test'
    with tempfile.NamedTemporaryFile(mode='w', dir=test_dir, delete=False) as f:
        try:
            f.close()
            yield Path(f.name)
        finally:
            try:
                os.unlink(f.name)
            except FileNotFoundError:
                # some tests may remove the file themselves
                pass


@contextmanager
def _tempdir(keep: bool = False) -> Iterator[Path]:
    _make_test_dir()
    d = tempfile.mkdtemp(dir=Path.cwd())
    try:
        yield Path(d)
        shutil.rmtree(d)
    except Exception:
        if not keep:
            shutil.rmtree(d)
        raise


def _write_file(f: Union[Path, IO[str]], contents: str) -> None:
    if isinstance(f, Path):
        f = f.open('w')
    try:
        f.write(contents)
    finally:
        f.close()
