from pathlib import Path

from psij import Job, JobSpec, JobExecutor
from _test_tools import assert_completed


def test_user_guide_redirect() -> None:
    ex = JobExecutor.get_instance('local')
    # DOC: start
    job = Job(
        JobSpec(
            executable='/bin/date',
            stdout_path=Path('/tmp/date.out'),
            stderr_path=Path('/tmp/date.err')
        )
    )
    # DOC: end
    ex.submit(job)
    status = job.wait()
    assert_completed(job, status)
