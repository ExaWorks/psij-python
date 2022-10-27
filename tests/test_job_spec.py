
import pytest

from psij import JobSpec

def test_environment_types() -> None:

    with pytest.raises(TypeError):
        JobSpec(environment={'foo': 1})                           # type: ignore

    with pytest.raises(TypeError):
        JobSpec(environment={1: 'foo'})                           # type: ignore

    with pytest.raises(TypeError):
        spec = JobSpec()
        spec.environment = {'foo': 1}                             # type: ignore

    spec = JobSpec()
    assert spec.environment is None

    spec = JobSpec(environment={'foo': 'bar'})
    assert spec.environment['foo'] == 'bar'                       # type: ignore

    spec = JobSpec()
    spec.environment = {'foo': 'bar'}
    assert spec.environment['foo'] == 'bar'

    spec.environment = {'foo': 'biz'}
    assert spec.environment['foo'] == 'biz'
