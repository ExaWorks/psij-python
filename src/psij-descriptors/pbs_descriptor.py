from distutils.version import StrictVersion

from psij.descriptor import Descriptor


__PSI_J_EXECUTORS__ = [Descriptor(name='pbs', nice_name='PBS Pro', aliases=['pbspro'],
                                  version=StrictVersion('0.2.0'),
                                  cls='psij.executors.batch.pbs.PBSJobExecutor'),
                       Descriptor(name='pbs_classic', nice_name='PBS Classic', aliases=['torque'],
                                  version=StrictVersion('0.2.0'),
                                  cls='psij.executors.batch.pbs_classic.PBSClassicJobExecutor')]
