from distutils.version import StrictVersion

from psij.descriptor import Descriptor


__PSI_J_EXECUTORS__ = [Descriptor(name="cobalt", version=StrictVersion("0.0.1"),
                                  cls='psij.executors.batch.cobalt.CobaltJobExecutor')]
