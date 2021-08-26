from pathlib import Path
from typing import Optional


class JobExecutorConfig(object):
    """An abstract configuration class for :class:`~psij.JobExecutor` instances."""

    def __init__(self, launcher_log_file: Optional[Path] = None):
        """
        Initializes a configuration object.

        :param launcher_log_file: If specified, log messages from launcher scripts (including
            output from pre- and post- launch scripts) will be directed to this file.
        """
        self.launcher_log_file = launcher_log_file

    DEFAULT: 'JobExecutorConfig' = None  # type: ignore


JobExecutorConfig.DEFAULT = JobExecutorConfig()
