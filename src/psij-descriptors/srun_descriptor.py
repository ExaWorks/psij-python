from packaging.version import Version
from psij.descriptor import Descriptor

__PSI_J_LAUNCHERS__ = [
    Descriptor(name='srun', version=Version('0.0.1'),
               cls='psij.launchers.srun.SrunLauncher'),
]
