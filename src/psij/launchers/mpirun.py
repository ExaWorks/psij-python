"""A module for `MPILauncher`."""
from pathlib import Path
from typing import Optional

from psij.job_executor_config import JobExecutorConfig
from psij.launchers import MultipleLauncher


class MPILauncher(MultipleLauncher):
    """Launches a job using `mpirun`."""

    _NAME_ = 'mpirun'

    def __init__(self, config: Optional[JobExecutorConfig] = None):
        """
        Initializes this launcher using an optional configuration.

        :param config: An optional configuration.
        """
        super().__init__(Path(__file__).parent / 'scripts' / 'mpi_launch.sh', config)


__PSI_J_LAUNCHERS__ = [MPILauncher]
