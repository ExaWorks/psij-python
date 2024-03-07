from pathlib import Path
from typing import Optional

from psij.executors.batch.pbs_base import PBSExecutorConfig, GenericPBSJobExecutor
from psij.executors.batch.script_generator import TemplatedScriptGenerator


class PBSJobExecutor(GenericPBSJobExecutor):
    """A :class:`~psij.JobExecutor` for PBS Pro and friends.

    This executor uses resource specifications specific to PBS Pro
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
                                             / 'pbspro.mustache')
        super().__init__(generator, url=url, config=config)
