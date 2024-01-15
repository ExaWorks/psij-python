from pathlib import Path
from typing import Optional

from psij.executors.batch.pbs_base import PBSExecutorConfig, GenericPBSJobExecutor
from psij.executors.batch.script_generator import TemplatedScriptGenerator


class PBSClassicJobExecutor(GenericPBSJobExecutor):
    """A :class:`~psij.JobExecutor` for classic PBS systems.

    This executor uses resource specifications specific to Open PBS. Specifically,
    this executor uses the `-l nodes=n:ppn=m` way of specifying nodes, which
    differs from the scheme used by PBS Pro.
    """

    def __init__(self, url: Optional[str] = None, config: Optional[PBSExecutorConfig] = None):
        """
        Parameters
        ----------
        url
            Not used, but required by the spec for automatic initialization.
        config
            An optional configuration for this executor.
        """
        if not config:
            config = PBSExecutorConfig()
        generator = TemplatedScriptGenerator(config, Path(__file__).parent / 'pbs'
                                             / 'pbs_classic.mustache')
        super().__init__(generator, url=url, config=config)
