"""A module for `MPILauncher`."""
from typing import List, cast, Optional, Tuple

from psi.j.job_executor_config import JobExecutorConfig
from psi.j.job_spec import JobSpec
from psi.j.launchers.launcher import Launcher
from psi.j.resource_spec import ResourceSpec, ResourceSpecV1


class MPILauncher(Launcher):
    """Launches a job using `mpirun`."""

    _NAME_ = 'mpirun'

    def __init__(self, config: Optional[JobExecutorConfig] = None):
        """
        Initializes this launcher using an optional configuration.

        :param config: An optional configuration.
        """
        super().__init__(config)

    def get_launch_command(self, spec: JobSpec) -> List[str]:
        """See :func:`~psi.j.Launcher.get_launch_command`."""
        np, ppn = self._get_resources(spec.resources)

        args = ['mpirun', '-np', str(np)]

        if ppn is not None:
            args += ['-npernode', str(ppn)]

        assert spec.executable is not None
        args += [spec.executable]

        if spec.arguments is not None:
            args += spec.arguments
        return args

    def _get_resources(self, res: Optional[ResourceSpec]) -> Tuple[int, Optional[int]]:
        if res is None:
            return 1, 1
        if res.version == 1:
            res1 = cast(ResourceSpecV1, res)
            return res1.computed_process_count, res1.processes_per_node
        else:
            raise ValueError('This launcher cannot handle resource specs with version {}'.
                             format(res.version))


__PSI_J_LAUNCHERS__ = [MPILauncher]
