#!/usr/bin/python3

def pytest_addoption(parser):
    parser.addoption('--executors', action='append', default=['local', 'batch-test', 'slurm'],
                     help='A set of executors to run the tests on.')


def pytest_generate_tests(metafunc):
    if 'executor' in metafunc.fixturenames:
        metafunc.parametrize('executor', metafunc.config.getoption('executors'))
