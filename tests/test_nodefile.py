import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from _test_tools import assert_completed
from executor_test_params import ExecutorTestParams
from psij import Job, JobSpec, JobExecutor, ResourceSpecV1

NOT_TESTED = set(['rp', 'flux'])


def test_nodefile(execparams: ExecutorTestParams) -> None:
    if execparams.executor in NOT_TESTED:
        pytest.skip('This test does not work with %s' % execparams.executor)

    my_path = os.path.dirname(os.path.realpath(__file__))

    N_PROC = 4
    with TemporaryDirectory(dir=Path.home() / '.psij' / 'test') as td:
        outp = Path(td, 'stdout.txt')
        spec = JobSpec('/bin/bash', [os.path.join(my_path, 'test_nodefile.sh'), str(N_PROC)],
                       stdout_path=outp)
        job = Job(spec)
        spec.resources = ResourceSpecV1(process_count=N_PROC)
        ex = JobExecutor.get_instance(execparams.executor)
        ex.submit(job)
        status = job.wait()
        assert_completed(job, status)
