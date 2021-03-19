"""A module containing the `SingleLauncher`."""
from typing import List, Optional

from psi.j.job_executor_config import JobExecutorConfig
from psi.j.job_spec import JobSpec
from psi.j.launchers.launcher import Launcher


class SingleLauncher(Launcher):
    """A launcher that launches a single copy of the executable. This is the default launcher."""

    _NAME_ = 'single'

    def __init__(self, config: Optional[JobExecutorConfig] = None):
        """
        Initializes this launcher using an optional configuration.

        :param config: An optional configuration.
        """
        super().__init__(config)

    def get_launch_command(self, spec: JobSpec) -> List[str]:
        """See :func:`~psi.j.Launcher.get_launch_command`."""
        assert spec.executable is not None
        args = [spec.executable]
        if spec.arguments is not None:
            args += spec.arguments
        return args


__PSI_J_LAUNCHERS__ = [SingleLauncher]
