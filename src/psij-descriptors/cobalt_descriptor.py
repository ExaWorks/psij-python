from distutils.version import StrictVersion

from psij.descriptor import Descriptor


__PSI_J_EXECUTORS__ = [Descriptor(name="cobalt", nice_name='Cobalt', version=StrictVersion("0.2.0"),
                                  cls='psij.executors.batch.cobalt.CobaltJobExecutor')]
