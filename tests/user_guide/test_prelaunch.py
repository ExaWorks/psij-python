import os
from pathlib import Path

from _test_tools import assert_completed, _deploy
from psij import Job, JobSpec, JobExecutor


def test_user_guide_pre_launch() -> None:
    script_dir = os.path.dirname(os.path.realpath(__file__))

    with _deploy(Path(script_dir) / 'pre_launch.sh') as pre_launch_sh_path:
        # START
        ex = JobExecutor.get_instance('local')
        spec = JobSpec('/bin/bash', ['-c', 'xmodule is-loaded test'])
        spec.pre_launch = pre_launch_sh_path

        job = Job(spec)
        ex.submit(job)
        status = job.wait()
        # END
        assert_completed(job, status)
