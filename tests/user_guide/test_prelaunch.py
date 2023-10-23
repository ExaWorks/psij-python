import os
from pathlib import Path

from psij import Job, JobSpec, JobExecutor, JobState


def test_user_guide_pre_launch() -> None:
    script_dir = os.path.dirname(os.path.realpath(__file__))

    ex = JobExecutor.get_instance('local')
    spec = JobSpec('/bin/bash', ['-c', 'module is-loaded test'])
    spec.pre_launch = Path(script_dir) / 'pre_launch.sh'

    job = Job(spec)
    ex.submit(job)
    status = job.wait()
    assert status is not None
    assert status.state == JobState.COMPLETED
