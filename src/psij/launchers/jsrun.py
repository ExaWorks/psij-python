"""A module for ``JsrunLauncher``."""

from pathlib import Path
from typing import Optional

from psij.job_executor_config import JobExecutorConfig
from psij.launchers import MultipleLauncher


class JsrunLauncher(MultipleLauncher):
    """Launches a job using LSF's ``jsrun``."""

    def __init__(self, config: Optional[JobExecutorConfig] = None):
        """
        Parameters
        ----------
        config
            An optional configuration.
        """
        super().__init__(Path(__file__).parent / 'scripts' / 'jsrun_launch.sh', config)
