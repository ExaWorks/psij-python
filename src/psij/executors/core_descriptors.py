from distutils.version import StrictVersion
from psij._descriptor import _Descriptor

__PSI_J_EXECUTORS__ = [
    _Descriptor(name='local', version=StrictVersion('0.0.1'),
                cls='psij.executors.local.LocalJobExecutor'),
    _Descriptor(name='batch-test', version=StrictVersion('0.0.1'),
                cls='psij.executors.batch._batch_test._TestJobExecutor'),
    _Descriptor(name='_always_loads', version=StrictVersion('0.0.1'),
                cls='psij.executors._always_loads_executor.AlwaysLoadsExecutor'),
    _Descriptor(name='_never_loads', version=StrictVersion('0.0.1'),
                cls='psij.executors._never_loads_executor.NeverLoadsExecutor')
]
