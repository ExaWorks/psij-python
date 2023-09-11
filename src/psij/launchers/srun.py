"""A module for `MPILauncher`."""
from pathlib import Path
from typing import Optional

from psij.job_executor_config import JobExecutorConfig
from psij.launchers import MultipleLauncher


class SrunLauncher(MultipleLauncher):
    """Launches a job using Slurm's ``srun``.

    See the
    `Slurm Workload Manager <https://slurm.schedmd.com/overview.html>`_.
    """

    _NAME_ = 'srun'

    def __init__(self, config: Optional[JobExecutorConfig] = None):
        """
        Parameters
        ----------
        config
            An optional configuration.
        """
        super().__init__(Path(__file__).parent / 'scripts' / 'srun_launch.sh', config)
