#!/usr/bin/env python3

# This is meant as a simple test file to check if psi/j was installed successfully

from distutils.version import Version

from psij import JobExecutor


def test_executor_version(name: str = 'local') -> None:
    exec = JobExecutor.get_instance(name)
    assert isinstance(exec.version, Version)
