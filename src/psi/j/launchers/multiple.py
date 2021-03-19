"""A module containing the `MultipleLauncher`."""

from pathlib import Path
from typing import List, cast, Optional

from psi.j.job_executor_config import JobExecutorConfig
from psi.j.job_spec import JobSpec
from psi.j.resource_spec import ResourceSpec, ResourceSpecV1
from psi.j.launchers import Launcher

SCRIPT_PATH = Path(__name__).parent / 'scripts' / 'multi_launch.sh'


class MultipleLauncher(Launcher):
    """
    A launcher that launches multiple identical copies of the executable.

    The exit code of the job corresponds to the first non-zero exit code encountered in one of the
    executable copies or zero if all invocations of the executable succeed.
    """

    _NAME_ = 'multiple'

    def __init__(self, config: Optional[JobExecutorConfig] = None):
        """
        Initializes this launcher using an optional configuration.

        :param config: An optional configuration.
        """
        super().__init__(config)

    def get_launch_command(self, spec: JobSpec) -> List[str]:
        """See :func:`~psi.j.Launcher.get_launch_command`."""
        assert spec.executable is not None
        args = ['/bin/bash', str(SCRIPT_PATH), str(self._get_count(spec.resources)),
                spec.executable]
        if spec.arguments is not None:
            args += spec.arguments
        return args

    def _get_count(self, res: Optional[ResourceSpec]) -> int:
        if res is None:
            return 1
        if res.version == 1:
            res1 = cast(ResourceSpecV1, res)
            return res1.computed_process_count
        else:
            raise ValueError('This launcher cannot handle resource specs with version {}'.
                             format(res.version))


__PSI_J_LAUNCHERS__ = [MultipleLauncher]
