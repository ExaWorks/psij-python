from packaging.version import Version
from psij.descriptor import Descriptor

__PSI_J_EXECUTORS__ = [
    Descriptor(name='local', nice_name='Local', version=Version('0.2.0'),
               cls='psij.executors.local.LocalJobExecutor')
]

__PSI_J_LAUNCHERS__ = [
    Descriptor(name='single', version=Version('0.2.0'),
               cls='psij.launchers.single.SingleLauncher'),
    Descriptor(name='multiple', version=Version('0.2.0'),
               cls='psij.launchers.multiple.MultipleLauncher'),
    Descriptor(name='mpirun', version=Version('0.2.0'),
               cls='psij.launchers.mpirun.MPILauncher'),
]
