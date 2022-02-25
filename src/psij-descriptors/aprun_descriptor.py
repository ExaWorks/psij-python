from distutils.version import StrictVersion

from psij.descriptor import Descriptor

__PSI_J_LAUNCHERS__ = [
    Descriptor(name='aprun', version=StrictVersion('0.0.1'),
               cls='psij.launchers.aprun.AprunLauncher'),
]
