from pathlib import Path
from typing import Type, Tuple

from psij.executors.batch.batch_scheduler_executor import SyncBatchSchedulerExecutor, \
    BatchScheduler, BatchSchedulerExecutorConfig, AsyncBatchSchedulerExecutor
from psij.executors.batch.pbs_base import PBSExecutorConfig, GenericPBSScheduler
from psij.executors.batch.script_generator import TemplatedScriptGenerator


class PBSScheduler(GenericPBSScheduler):
    """A BatchScheduler class for PBS."""

    def __init__(self, config: PBSExecutorConfig) -> None:
        """
        Parameters
        ----------
        config
            A configuration to use for this instance.
        """
        generator = TemplatedScriptGenerator(
            config, Path(__file__).parent / 'pbs' / 'pbspro.mustache'
        )
        super().__init__(generator)


class PBSJobExecutor(SyncBatchSchedulerExecutor):
    """A synchronous job executor for PBS Pro."""

    def get_concrete_classes(self) \
            -> Tuple[Type[BatchScheduler], Type[BatchSchedulerExecutorConfig]]:
        """See :meth:`~.BatchSchedulerExecutor.get_concrete_classes`"""
        return PBSScheduler, PBSExecutorConfig


class AsyncPBSJobExecutor(AsyncBatchSchedulerExecutor):
    """An asynchronous job executor for PBS Pro."""

    def get_concrete_classes(self) \
            -> Tuple[Type[BatchScheduler], Type[BatchSchedulerExecutorConfig]]:
        """See :meth:`~.BatchSchedulerExecutor.get_concrete_classes`"""
        return PBSScheduler, PBSExecutorConfig
