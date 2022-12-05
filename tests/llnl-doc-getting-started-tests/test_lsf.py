"""Tests the code snippets from the 'getting started' psij docs. This test suite is for LSF"""
import base_getting_started_doc_tests as doc_tests

compute_env = "lsf"

def test_getting_started_basic_usage_slurm() -> None:
    doc_tests.getting_started_basic_usage(compute_env)


def test_getting_started_adding_complexity_slurm() -> None:
    doc_tests.getting_started_adding_complexity(compute_env)


def test_getting_started_status_callback_slurm() -> None:
    doc_tests.getting_started_status_callbacks(compute_env)


def test_llnl_slurm() -> None:
    doc_tests.our_test(compute_env)