import os
import shutil
from pathlib import Path

from psij import Job, JobSpec, JobExecutor, StageOut, StageOutFlags, JobExecutorConfig
from _test_tools import _tempdir


def test_user_guide_simple_staging() -> None:
    ex = JobExecutor.get_instance('local')
    script_dir = os.path.dirname(os.path.realpath(__file__))
    script_path = Path(script_dir) / 'fake_app.sh'

    with _tempdir() as jobdir:
        shutil.copy(script_path, jobdir / 'app.sh')

        # DOC: start
        spec = JobSpec('/bin/bash', ['app.sh', '--out', 'out.txt', '--log', 'log.txt'],
                       directory=jobdir,
                       stderr_path='err.txt',
                       stage_out=[
                           StageOut('out.txt', 'out.txt',
                                    StageOutFlags.ON_SUCCESS | StageOutFlags.IF_PRESENT),
                           StageOut('log.txt', 'log.txt',
                                    StageOutFlags.ON_ERROR)
                       ])
        job = Job(spec)
        ex.run(job)
        # DOC: end