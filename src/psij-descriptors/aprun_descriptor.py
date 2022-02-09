from distutils.version import StrictVersion

from psij._descriptor import _Descriptor

__PSI_J_LAUNCHERS__ = [
    _Descriptor(name='aprun', version=StrictVersion('0.0.1'),
                cls='psij.launchers.aprun.AprunLauncher'),
]
