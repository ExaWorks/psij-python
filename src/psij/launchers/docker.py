"""A module containing the `MultipleLauncher`."""

from pathlib import Path
from typing import List, cast, Optional, Dict

from psij import BaseJob, InvalidJobException
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

    def __init__(self, script_path: Path = Path(__file__).parent / 'scripts' / 'docker_launch.sh',
                 config: Optional[JobExecutorConfig] = None):
        """
        Parameters
        ----------
        config
            An optional configuration.
        """
        super().__init__(script_path=script_path, config=config)

    def get_additional_args(self, job: BaseJob) -> List[str]:
        """See \
        :func:`~psij.launchers.script_based_launcher.ScriptBasedLauncher.get_additional_args`."""
        spec = job.spec
        assert spec is not None
        attrs = spec.attributes

        if attrs is None or attrs.custom_attributes is None:
            raise InvalidJobException('Missing job attributes needed by the docker launcher.')

        docker_args = self._get_args(attrs.custom_attributes)

        container_spec = docker_args.pop('spec', None)
        image_id = docker_args.pop('image_id', None)
        container_id = docker_args.pop('container_id', None)
        n = sum(1 for x in [container_spec, container_id, image_id] if x is not None)
        if n != 1:
            raise InvalidJobException('The docker launcher requires one and only one of the '
                                      '"docker.spec", "docker.image_id", or "docker.container_id" '
                                      'attributes to be specified')

        l = []

        if container_spec is not None:
            l += ['spec', str(container_spec)]
        elif image_id is not None:
            l += ['image', str(image_id)]
        else:
            l += ['container', str(container_id)]

        for k, v in docker_args.items():
            l += [f'--{k}', str(v)]

        return l


    def _get_args(self, attrs: Dict[str, object]) -> Dict[str, object]:
        r = {}
        for k, v in attrs.items():
            if k.startswith('docker.'):
                k2 = k[7:]
                r[k2] = v
        return r
