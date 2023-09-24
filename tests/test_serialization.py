from datetime import timedelta
from pathlib import Path

from psij import JobSpec, ResourceSpecV1, JobAttributes
from psij.serialize import JSONSerializer


def test_serialization() -> None:
    s = JSONSerializer()

    spec1 = JobSpec(
        name='test',
        executable='/bin/sleep',
        arguments=['1'],
        directory=Path('/tmp'),
        inherit_environment=True,
        environment={'VAR1': 'value1', 'VAR2': 'value2'},
        resources=ResourceSpecV1(node_count=1, exclusive_node_use=False),
        attributes=JobAttributes(
            duration=timedelta(minutes=10),
            custom_attributes={'ATTR1': 'value1', 'ATTR2': 'value2'}
        ),
        launcher="single"
    )

    str1 = s.dumps(spec1)

    spec2 = s.loads(str1)
    assert spec1 == spec2

    str2 = s.dumps(spec2)
    assert str1 == str2
