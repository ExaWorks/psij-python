from packaging.version import Version
from psij.descriptor import Descriptor


__PSI_J_EXECUTORS__ = [Descriptor(name='lsf', nice_name='LSF', version=Version('0.2.0'),
                                  cls='psij.executors.batch.lsf.LsfJobExecutor')]
