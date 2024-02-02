from tempfile import NamedTemporaryFile

from executor_test_params import ExecutorTestParams
from _test_tools import _get_executor_instance, _get_timeout, assert_completed, _make_test_dir
from psij import Job, JobSpec


def test_stagein(execparams: ExecutorTestParams) -> None:
    with NamedTemporaryFile(delete=False) as outf:
        outf.close()
        with NamedTemporaryFile(mode='w', delete=False) as f:

            f.write('ABCD')
            f.close()

            job = Job(JobSpec(executable='/bin/cat', stdout_path=outf.name,
                              launcher=execparams.launcher))
            ex = _get_executor_instance(execparams, job)
            ex.submit(job)
            status = job.wait(timeout=_get_timeout(execparams))
            assert_completed(job, status)

            with open(outf, 'r') as out:
                result = out.read()
            assert result.strip() == 'ABCD'
