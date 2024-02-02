import os
from pathlib import Path

from _test_tools import assert_completed
from psij import Job, JobSpec, JobExecutor, JobState


def test_user_guide_pre_launch() -> None:
    script_dir = os.path.dirname(os.path.realpath(__file__))

    # START
    ex = JobExecutor.get_instance('local')
    spec = JobSpec('/bin/bash', ['-c', 'module is-loaded test'])
    spec.pre_launch = Path(script_dir) / 'pre_launch.sh'

    job = Job(spec)
    ex.submit(job)
    status = job.wait()
    # END
    assert_completed(job, status)
