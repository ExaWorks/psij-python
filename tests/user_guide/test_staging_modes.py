import os
from pathlib import Path

from psij import Job, JobSpec, JobExecutor, StageOut, StagingMode
from _test_tools import _tempdir, _write_file
from psij import StageIn


def test_user_guide_simple_staging() -> None:
    ex = JobExecutor.get_instance('local')
    with _tempdir() as srcdir, _tempdir() as jobdir:
        os.chdir(srcdir)
        _write_file('a.txt', 'ABCD')

        # DOC: start
        inf = Path('a.txt')
        outf = Path('b.txt')

        job = Job(JobSpec('/bin/cat', ['in.txt'],
                          directory=jobdir,
                          stdout_path='out.txt',
                          # a link to in.txt will be created in the job directory
                          stage_in=[StageIn(inf, 'in.txt', mode=StagingMode.LINK)],
                          # out.txt will be moved to $PWD/b.txt
                          stage_out=[StageOut('out.txt', outf, mode=StagingMode.MOVE)]))

        ex.run(job)
        # DOC: end
        with open('b.txt', 'r') as f:
            content = f.read()
        assert content == 'ABCD'
        infj = jobdir / 'in.txt'
        assert infj.exists()
        assert infj.is_symlink()

        outfj = jobdir / 'out.txt'
        assert not outfj.exists()
