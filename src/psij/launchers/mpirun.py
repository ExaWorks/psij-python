"""A module for `MPILauncher`."""
from pathlib import Path
from typing import Optional

from psij.job_executor_config import JobExecutorConfig
from psij.launchers import MultipleLauncher


class MPILauncher(MultipleLauncher):
    """Launches jobs using ``mpirun``.

    ``mpirun`` is a tool provided by
    `MPI <https://www.mpi-forum.org/>`_ implementations, such as
    `Open MPI <https://www.open-mpi.org/>`_.
    """

    def __init__(self, config: Optional[JobExecutorConfig] = None):
        """
        Parameters
        ----------
        config
            An optional configuration.
        """
        super().__init__(Path(__file__).parent / 'scripts' / 'mpi_launch.sh', config)
