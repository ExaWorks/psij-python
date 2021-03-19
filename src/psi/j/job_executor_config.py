class JobExecutorConfig(object):
    """An abstract configuration class for :class:`~psi.j.JobExecutor` instances."""

    DEFAULT: 'JobExecutorConfig' = None  # type: ignore


JobExecutorConfig.DEFAULT = JobExecutorConfig()
