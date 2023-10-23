"""A module containing the `MultipleLauncher`."""

from pathlib import Path
from typing import List, cast, Optional

from psij.job import Job
from psij.job_executor_config import JobExecutorConfig
from psij.launchers.script_based_launcher import ScriptBasedLauncher
from psij.resource_spec import ResourceSpec, ResourceSpecV1

SCRIPT_PATH = Path(__name__).parent / 'scripts' / 'multi_launch.sh'


class MultipleLauncher(ScriptBasedLauncher):
    """
    A launcher that launches multiple identical copies of the executable.

    The exit code of the job corresponds to the first non-zero exit code encountered in one of the
    executable copies or zero if all invocations of the executable succeed.
    """

    def __init__(self, script_path: Path = Path(__file__).parent / 'scripts' / 'multi_launch.sh',
                 config: Optional[JobExecutorConfig] = None):
        """
        Parameters
        ----------
        config
            An optional configuration.
        """
        super().__init__(script_path=script_path, config=config)

    def get_additional_args(self, job: Job) -> List[str]:
        """See \
        :func:`~psij.launchers.script_based_launcher.ScriptBasedLauncher.get_additional_args`."""
        spec = job.spec
        assert spec is not None
        return [str(self._get_count(spec.resources))]

    def _get_count(self, res: Optional[ResourceSpec]) -> int:
        if res is None:
            return 1
        if res.version == 1:
            res1 = cast(ResourceSpecV1, res)
            return res1.computed_process_count
        else:
            raise ValueError('This launcher cannot handle resource specs with version {}'.
                             format(res.version))
