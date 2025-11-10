from packaging.version import Version
from psij.descriptor import Descriptor


__PSI_J_EXECUTORS__ = [Descriptor(name='slurm', nice_name='Slurm', version=Version('0.2.0'),
                                  cls='psij.executors.batch.slurm.SlurmJobExecutor')]
