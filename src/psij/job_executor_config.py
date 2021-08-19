from pathlib import Path
from typing import Optional


class JobExecutorConfig(object):
    """An abstract configuration class for :class:`~psij.JobExecutor` instances."""

    DEFAULT: 'JobExecutorConfig' = None  # type: ignore
    DEFAULT_WORK_DIRECTORY = Path.home() / '.psij' / 'work'

    def __init__(self, launcher_log_file: Optional[Path] = None,
                 work_directory: Optional[Path] = None):
        """
        Initializes a configuration object.

        :param launcher_log_file: If specified, log messages from launcher scripts (including
            output from pre- and post- launch scripts) will be directed to this file.
        """
        self.launcher_log_file = launcher_log_file
        if work_directory:
            self.work_directory = work_directory
        else:
            self.work_directory = JobExecutorConfig.DEFAULT_WORK_DIRECTORY


JobExecutorConfig.DEFAULT = JobExecutorConfig()
