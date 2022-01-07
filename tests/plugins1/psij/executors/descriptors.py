from distutils.version import StrictVersion
from psij._descriptor import _Descriptor

__PSI_J_EXECUTORS__ = [
    # executor in the same path as descriptor; should load
    _Descriptor(name='p1-tp1', version=StrictVersion('0.0.1'),
                cls='_test_plugins1.ex1._Executor1'),
    # executor in different path, but sharing module; should NOT load
    _Descriptor(name='p2-tp1', version=StrictVersion('0.0.1'),
                cls='_test_plugins1.ex2._Executor2'),
    # executor in different path with no shared module; should NOT load
    _Descriptor(name='p2-tp3', version=StrictVersion('0.0.1'),
                cls='_test_plugins3.ex3._Executor3'),
]
