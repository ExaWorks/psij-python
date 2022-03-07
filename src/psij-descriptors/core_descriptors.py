from distutils.version import StrictVersion
from psij.descriptor import Descriptor

__PSI_J_EXECUTORS__ = [
    Descriptor(name='local', version=StrictVersion('0.0.1'),
               cls='psij.executors.local.LocalJobExecutor')
]

__PSI_J_LAUNCHERS__ = [
    Descriptor(name='single', version=StrictVersion('0.0.1'),
               cls='psij.launchers.single.SingleLauncher'),
    Descriptor(name='multiple', version=StrictVersion('0.0.1'),
               cls='psij.launchers.multiple.MultipleLauncher'),
    Descriptor(name='mpirun', version=StrictVersion('0.0.1'),
               cls='psij.launchers.mpirun.MPILauncher'),
]
