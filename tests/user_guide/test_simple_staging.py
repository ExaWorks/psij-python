import os
from pathlib import Path

from psij import Job, JobSpec, JobExecutor, StageOut
from _test_tools import _tempdir
from psij import StageIn


def test_user_guide_simple_staging() -> None:
    ex = JobExecutor.get_instance('local')
    with _tempdir() as srcdir, _tempdir() as jobdir:
        os.chdir(srcdir)
        with open('a.txt', 'w') as f:
            f.write('ABCD')

        # DOC: start
        inf = Path('a.txt')
        outf = Path('b.txt')

        job = Job(JobSpec('/bin/cat', ['in.txt'],
                          directory=jobdir,  # DOC: skip
                          stdout_path='out.txt',
                          stage_in=[StageIn(inf, 'in.txt')],
                          stage_out=[StageOut('out.txt', outf)]))

        ex.run(job)
        # DOC: end
        with open('b.txt', 'r') as f:
            content = f.read()
        assert content == 'ABCD'
