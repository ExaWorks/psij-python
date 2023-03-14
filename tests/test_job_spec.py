
import pytest

from psij import JobSpec, JobExecutor, Job


def _test_spec(spec: JobSpec) -> None:
    ex = JobExecutor.get_instance('local')
    ex.submit(Job(spec))


def test_environment_types() -> None:

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

    spec.environment = {'foo': 'biz', 'bar': 42}
    assert spec.environment['foo'] == 'biz'
    assert spec.environment['bar'] == '42'


test_environment_types()
