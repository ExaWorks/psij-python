import logging
from pathlib import Path
from typing import Optional

import pytest

from psij import Job, JobSpec, ResourceSpecV1, InvalidJobException
from tempfile import TemporaryDirectory

from executor_test_params import ExecutorTestParams
from _test_tools import _get_executor_instance, _get_timeout, assert_completed, _make_test_dir


logger = logging.getLogger(__name__)


def test_resource_constraints() -> None:
    ResourceSpecV1()
    ResourceSpecV1(process_count=2)
    ResourceSpecV1(node_count=2)
    ResourceSpecV1(processes_per_node=2)
    ResourceSpecV1(process_count=4, node_count=2)
    ResourceSpecV1(process_count=4, processes_per_node=2)
    ResourceSpecV1(process_count=4, node_count=2, processes_per_node=2)


def _failingResourceSpecV1(node_count: Optional[int] = None, process_count: Optional[int] = None,
                           processes_per_node: Optional[int] = None) -> None:
    try:
        ResourceSpecV1(node_count=node_count, process_count=process_count,
                       processes_per_node=processes_per_node)
        pytest.fail('Should have failed: process_count=%s, node_count=%s, ppn=%s' %
                    (process_count, node_count, processes_per_node))
    except InvalidJobException:
        pass


def test_failing_resource_constraints() -> None:
    _failingResourceSpecV1(process_count=3, node_count=2)
    _failingResourceSpecV1(process_count=3, processes_per_node=2)
    _failingResourceSpecV1(process_count=8, node_count=2, processes_per_node=2)


def _check_ranks(s: str, expected_ranks: int, expected_nodes: int) -> None:
    lines = s.splitlines()
    unique_hosts = set()
    rank_count = 0

    for line in lines:
        line = line.strip()
        if line == '':
            continue
        rank_count += 1
        unique_hosts.add(line)

    if len(unique_hosts) != expected_nodes:
        pytest.fail('Wrong number of nodes. Expected %s, got %s' % (expected_nodes, unique_hosts))
    if rank_count != expected_ranks:
        pytest.fail('Wrong number of ranks. Expected %s, got %s' % (expected_ranks, rank_count))


def test_nodes(execparams: ExecutorTestParams) -> None:
    if not _supported(execparams):
        pytest.skip('Unsupported executor/launcher combination')

    _make_test_dir()

    n_ranks = 4
    n_nodes = 2
    ppn = n_ranks // n_nodes

    with TemporaryDirectory(dir=Path.home() / '.psij' / 'test') as td:
        outp = Path(td, 'stdout.txt')
        job = Job(JobSpec(executable='/bin/hostname', stdout_path=outp,
                          launcher=execparams.launcher))
        assert job.spec is not None
        job.spec.resources = ResourceSpecV1(node_count=n_nodes, processes_per_node=ppn)
        ex = _get_executor_instance(execparams, job)
        ex.submit(job)
        status = job.wait(timeout=_get_timeout(execparams))
        assert_completed(job, status)

        with open(outp, 'r') as outf:
            result = outf.read()
        logger.info("Output from job: %s", result)

        _check_ranks(result, n_ranks, n_nodes)


def _supported(ep: ExecutorTestParams) -> bool:
    if ep.executor == 'batch-test':
        return ep.launcher == 'batch-test'
    if ep.executor in ['slurm', 'pbs', 'lsf']:
        return ep.launcher in ['mpirun', 'srun', 'ibrun']

    return False


def test_memory(execparams: ExecutorTestParams) -> None:
    job = Job(JobSpec(executable='/bin/hostname', launcher=execparams.launcher))
    assert job.spec is not None
    job.spec.resources = ResourceSpecV1(memory=1024 * 1024 * 100)
    ex = _get_executor_instance(execparams, job)
    ex.submit(job)
    status = job.wait(timeout=_get_timeout(execparams))
    assert_completed(job, status)
