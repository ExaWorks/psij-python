from distutils.version import StrictVersion
from psij._descriptor import _Descriptor

__PSI_J_EXECUTORS__ = [
    _Descriptor(name='local', version=StrictVersion('0.0.1'),
                cls='psij.executors.local.LocalJobExecutor'),
    _Descriptor(name='batch-test', version=StrictVersion('0.0.1'),
                cls='psij.executors.batch._batch_test._TestJobExecutor')
]

__PSI_J_LAUNCHERS__ = [
    _Descriptor(name='single', version=StrictVersion('0.0.1'),
                cls='psij.launchers.single.SingleLauncher'),
    _Descriptor(name='multiple', version=StrictVersion('0.0.1'),
                cls='psij.launchers.multiple.MultipleLauncher'),
    _Descriptor(name='mpirun', version=StrictVersion('0.0.1'),
                cls='psij.launchers.mpirun.MPILauncher'),
]
