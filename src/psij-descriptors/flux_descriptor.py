from distutils.version import StrictVersion

from psij.descriptor import Descriptor


__PSI_J_EXECUTORS__ = [Descriptor(name='flux', nice_name='Flux', version=StrictVersion('0.0.1'),
                                  cls='psij.executors.flux.FluxJobExecutor')]
