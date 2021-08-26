"""A module containing the `SingleLauncher`."""
from pathlib import Path
from typing import Optional

from psij.job_executor_config import JobExecutorConfig
from psij.launchers.script_based_launcher import ScriptBasedLauncher


class SingleLauncher(ScriptBasedLauncher):
    """A launcher that launches a single copy of the executable. This is the default launcher."""

    _NAME_ = 'single'

    def __init__(self, config: Optional[JobExecutorConfig] = None):
        """
        Initializes this launcher using an optional configuration.

        :param config: An optional configuration.
        """
        super().__init__(Path(__file__).parent / 'scripts' / 'single_launch.sh', config)


__PSI_J_LAUNCHERS__ = [SingleLauncher]
