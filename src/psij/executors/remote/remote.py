from datetime import timedelta

from abc import abstractmethod
from pathlib import Path

from typing import Optional

from psij import AsyncJobExecutor
from psij.job_executor import JobExecutor
from psij.job_executor_config import JobExecutorConfig


class RemoteJobExecutorConfig(JobExecutorConfig):
    def __init__(self, remote_name: str = 'local',
                 remote_config: Optional[JobExecutorConfig] = None) -> None:
        """
        Generic configuration for remote executor implementations.

        Remote executors work by forwarding jobs to a service which then
        delegates the actual execution to another executor.

        Parameters
        ----------
        remote_name
            The type of the remote executor to use on the server for executing
            jobs. This can be any name supported by the PSI/J library instance
            deployed and used by the service, which will generally depend on
            how PSI/J is configured on the server side. The precise list can
            be obtained using
            :meth:`psij.RemoteJobExecutor.get_remote_executor_names()`
        remote_config:
            A configuration to be passed to the remote job executor.
        """
        super().__init__()
        self.remote_name = remote_name
        self.remote_config = remote_config


class RemoteJobExecutor(JobExecutor):
    """A base class for remote executors.

    This class does nothing more than provide a constructor that takes a
    :class:`~.RemoteJobExecutorConfig` as configuration.
    """

    def __init__(self, url: Optional[str] = None,
                 config: Optional[RemoteJobExecutorConfig] = None):
        if config is None:
            config = RemoteJobExecutorConfig()
        super().__init__(url=url, config=config)


class AsyncRemoteJobExecutor(AsyncJobExecutor):
    """An async version of :class:`~psij.RemoteJobExecutor`."""

    def __init__(self, url: Optional[str] = None,
                 config: Optional[RemoteJobExecutorConfig] = None):
        if config is None:
            config = RemoteJobExecutorConfig()
        super().__init__(url=url, config=config)
