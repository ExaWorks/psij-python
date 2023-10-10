from pathlib import Path
from typing import Optional, Union


class JobExecutorConfig(object):
    """An abstract configuration class for :class:`~psij.JobExecutor` instances."""

    #: A default `JobExecutorConfig` used when none is specified.
    DEFAULT: 'JobExecutorConfig' = None  # type: ignore

    #: The default work directory when a work directory is not explicitly specified.
    DEFAULT_WORK_DIRECTORY = Path.home() / '.psij' / 'work'

    def __init__(self, launcher_log_file: Optional[Path] = None,
                 work_directory: Optional[Path] = None) -> None:
        """
        Parameters
        ----------
        launcher_log_file
            If specified, log messages from launcher scripts (including
            output from pre- and post- launch scripts) will be directed to this file.
        work_directory
            A directory where submit scripts and auxiliary job files will be generated. In a,
            cluster this directory needs to point to a directory on a shared filesystem. This is so
            that the exit code file, likely written on a service node, can be accessed by PSI/J,
            likely running on a head node.
        """
        self._launcher_log_file = launcher_log_file

        if work_directory:
            self._work_directory = work_directory
        else:
            self._work_directory = JobExecutorConfig.DEFAULT_WORK_DIRECTORY

    @property
    def launcher_log_file(self) -> Optional[Path]:
        """
        Configure the executor's launcher log file.

        Parameters
        ----------
        launcher_log_file
            If specified, log messages from launcher scripts (including
            output from pre- and post- launch scripts) will be directed to this file.
        """
        return self._launcher_log_file

    @launcher_log_file.setter
    def launcher_log_file(self, value: Optional[Union[str, Path]]) -> None:
        if value:
            self._launcher_log_file = Path(value)

    @property
    def work_directory(self) -> Path:
        """
        Configure the execor's work directory.

        Parameters
        ----------
        work_directory
            A directory where submit scripts and auxiliary job files will be generated. In a,
            cluster this directory needs to point to a directory on a shared filesystem. This is so
            that the exit code file, likely written on a service node, can be accessed by PSI/J,
            likely running on a head node.
        """
        return self._work_directory

    @work_directory.setter
    def work_directory(self, value: Union[str, Path]) -> None:
        self._work_directory = Path(value)


JobExecutorConfig.DEFAULT = JobExecutorConfig()
