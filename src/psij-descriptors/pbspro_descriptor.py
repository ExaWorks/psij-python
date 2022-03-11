from distutils.version import StrictVersion

from psij.descriptor import Descriptor


__PSI_J_EXECUTORS__ = [Descriptor(name='pbspro', version=StrictVersion('0.0.1'),
                                  cls='psij.executors.batch.pbspro.PBSProJobExecutor')]
