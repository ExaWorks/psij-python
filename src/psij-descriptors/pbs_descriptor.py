from packaging.version import Version
from psij.descriptor import Descriptor


__PSI_J_EXECUTORS__ = [Descriptor(name='pbs', nice_name='PBS Pro', aliases=['pbspro'],
                                  version=Version('0.0.2'),
                                  cls='psij.executors.batch.pbs.PBSJobExecutor'),
                       Descriptor(name='pbs_classic', nice_name='PBS Classic', aliases=['torque'],
                                  version=Version('0.0.2'),
                                  cls='psij.executors.batch.pbs_classic.PBSClassicJobExecutor')]
