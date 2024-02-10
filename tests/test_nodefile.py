import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from _test_tools import assert_completed, _get_executor_instance, _deploy
from executor_test_params import ExecutorTestParams
from psij import Job, JobSpec, ResourceSpecV1

NOT_TESTED = set(['rp', 'flux'])


def test_nodefile(execparams: ExecutorTestParams) -> None:
    if execparams.executor in NOT_TESTED:
        pytest.skip('This test does not work with %s' % execparams.executor)
    if execparams.launcher == 'single':
        pytest.skip('This test does not work with the single launcher')

    my_path = os.path.dirname(os.path.realpath(__file__))

    N_PROC = 4
    with TemporaryDirectory(dir=Path.home() / '.psij' / 'test') as td:
        outp = Path(td, 'stdout.txt')
        with _deploy(os.path.join(my_path, 'test_nodefile.sh')) as excp:
            spec = JobSpec('/bin/bash', [str(excp), str(N_PROC)],
                           stdout_path=outp)
            job = Job(spec)
            spec.resources = ResourceSpecV1(process_count=N_PROC)
            ex = _get_executor_instance(execparams, job)
            ex.submit(job)
            status = job.wait()
            assert_completed(job, status)
