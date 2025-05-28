from packaging.version import Version
from psij.descriptor import Descriptor

__PSI_J_EXECUTORS__ = [Descriptor(name='nqsv', version=Version('0.0.1'),
                                  cls='psij.executors.batch.nqsv.NQSVJobExecutor')]
