from distutils.version import StrictVersion

from psij._descriptor import _Descriptor


_PSI_J_EXECUTORS__ = [_Descriptor(name="cobalt", version=StrictVersion("0.0.1"),
                                  cls='psij.executors.batch.cobalt.CobaltJobExecutor')]
