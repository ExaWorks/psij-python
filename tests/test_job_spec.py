import os
from pathlib import Path

from typeguard import suppress_type_checks

import pytest

from psij import Job, JobExecutor, JobSpec


def _test_spec(spec: JobSpec) -> None:
    ex = JobExecutor.get_instance('local')
    ex.submit(Job(spec))


def test_environment_types() -> None:

    with suppress_type_checks():
        with pytest.raises(TypeError):
            _test_spec(JobSpec(executable='true', environment={1: 'foo'}))  # type: ignore

    with pytest.raises(TypeError):
        spec = JobSpec(executable='true')
        spec.environment = {'foo': 'bar'}
        spec.environment['buz'] = [2]  # type: ignore
        _test_spec(spec)

    spec = JobSpec()
    assert spec.environment is None

    spec = JobSpec(environment={'foo': 'bar'})
    assert spec.environment['foo'] == 'bar'  # type: ignore

    spec = JobSpec()
    spec.environment = {'foo': 'bar'}
    assert spec.environment['foo'] == 'bar'

    spec.environment = {'foo': 'biz', 'bar': 42}  # type: ignore
    assert spec.environment['foo'] == 'biz'
    assert spec.environment['bar'] == '42'


def test_path_conversion() -> None:
    assert JobSpec(directory=os.path.join("test", "path")).directory == Path("test") / "path"
    assert JobSpec(stdin_path=os.path.join("test", "path")).stdin_path == Path("test") / "path"
    assert JobSpec(stdout_path=os.path.join("test", "path")).stdout_path == Path("test") / "path"
    assert JobSpec(stderr_path=os.path.join("test", "path")).stderr_path == Path("test") / "path"
    assert JobSpec(pre_launch=os.path.join("test", "path")).pre_launch == Path("test") / "path"
    assert JobSpec(post_launch=os.path.join("test", "path")).post_launch == Path("test") / "path"
