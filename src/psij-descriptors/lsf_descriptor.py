from distutils.version import StrictVersion

from psij.descriptor import Descriptor


__PSI_J_EXECUTORS__ = [Descriptor(name='lsf', nice_name='LSF', version=StrictVersion('0.0.1'),
                                  cls='psij.executors.batch.lsf.LsfJobExecutor')]
