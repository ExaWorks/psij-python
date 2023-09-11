"""A module for ``AprunLauncher``."""

from pathlib import Path
from typing import Optional

from psij.job_executor_config import JobExecutorConfig
from psij.launchers import MultipleLauncher


class AprunLauncher(MultipleLauncher):
    """Launches a job using Cobalt's ``aprun``."""

    def __init__(self, config: Optional[JobExecutorConfig] = None):
        """
        Parameters
        ----------
        config
            An optional configuration.
        """
        super().__init__(Path(__file__).parent / 'scripts' / 'aprun_launch.sh', config)
