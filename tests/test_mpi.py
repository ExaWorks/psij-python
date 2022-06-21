import logging
from pathlib import Path

import pytest

from psij import Job, JobSpec, ResourceSpecV1
from tempfile import TemporaryDirectory

from executor_test_params import ExecutorTestParams
from _test_tools import _get_executor_instance, _get_timeout, assert_completed, _make_test_dir


RANK_VARS = ['PMIX_RANK', 'OMPI_COMM_WORLD_RANK', 'PMI_RANK', 'MV2_COMM_WORLD_RANK']
logger = logging.getLogger(__name__)


def _check_ranks(s: str, rank_var: str, n: int) -> bool:
    expected = set([str(x) for x in range(n)])
    lines = s.splitlines()

    rank_var = rank_var + '='
    for line in lines:
        if line.startswith(rank_var):
            value = line[len(rank_var):]
            if value not in expected:
                pytest.fail('Unexpected rank value in output: %s' % value)
            expected.remove(value)

    if len(expected) == 0:
        return True
    if len(expected) == n:
        return False

    pytest.fail('Only some of the expected ranks were found in output. Missing ranks: %s'
                % expected)


def test_basic_mpi(execparams: ExecutorTestParams) -> None:
    if execparams.launcher != 'mpirun':
        pytest.skip('This test requires mpirun')

    _make_test_dir()

    n_ranks = 4

    with TemporaryDirectory(dir=Path.home() / '.psij' / 'test') as td:
        outp = Path(td, 'stdout.txt')
        errp = Path(td, 'stderr.txt')
        job = Job(JobSpec(executable='/bin/bash', arguments=['-c', 'env | grep RANK'],
                          stdout_path=outp, stderr_path=errp, launcher=execparams.launcher))
        assert job.spec is not None
        job.spec.resources = ResourceSpecV1(process_count=n_ranks)
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert_completed(job, status)

        with open(outp, 'r') as outf:
            result = outf.read()
        logger.info("Output from job: %s", result)

        for rank_var in RANK_VARS:
            if _check_ranks(result, rank_var, n_ranks):
                # success
                return
        pytest.fail('No rank variables found in output')
