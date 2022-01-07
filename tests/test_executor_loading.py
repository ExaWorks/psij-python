from psij import JobExecutor


def test_executor_loading() -> None:
    je1 = JobExecutor.get_instance('_always_loads')
    assert je1 is not None

    try:
        JobExecutor.get_instance('_never_loads')
        assert False
    except Exception:
        pass


def test_cross_path_loading1() -> None:
    JobExecutor.get_instance('p1-tp1')


def test_cross_path_loading2() -> None:
    try:
        # this should fail since the descriptor and executor are under different paths
        # despite the executor being in the same package as p1-tp1 which should load
        JobExecutor.get_instance('p2-tp1')
        assert False
    except ValueError as ve:
        assert 'Unable to load executor' in str(ve)


def test_cross_path_loading3() -> None:
    try:
        # this should fail since the descriptor and executor are under different paths
        JobExecutor.get_instance('p2-tp3')
        assert False
    except ValueError as ve:
        assert 'Unable to load executor' in str(ve)
