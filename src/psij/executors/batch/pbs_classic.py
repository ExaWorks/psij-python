from pathlib import Path
from typing import Type, Tuple

from psij.executors.batch.batch_scheduler_executor import SyncBatchSchedulerExecutor, \
    BatchScheduler, BatchSchedulerExecutorConfig, AsyncBatchSchedulerExecutor
from psij.executors.batch.pbs_base import PBSExecutorConfig, GenericPBSScheduler
from psij.executors.batch.script_generator import TemplatedScriptGenerator


class PBSClassicScheduler(GenericPBSScheduler):
    """A :class:`~.BatchScheduler` for classic PBS."""

    def __init__(self, config: PBSExecutorConfig) -> None:
        """
        Parameters
        ----------
        config
            A configuration to use for this instance.
        """
        generator = TemplatedScriptGenerator(
            config, Path(__file__).parent / 'pbs' / 'pbs_classic.mustache'
        )
        super().__init__(generator)


class PBSClassicJobExecutor(SyncBatchSchedulerExecutor):
    """Synchronous job executor for class PBS schedulers."""

    def get_concrete_classes(self) \
            -> Tuple[Type[BatchScheduler], Type[BatchSchedulerExecutorConfig]]:
        """See :meth:`~.BatchSchedulerExecutor.get_concrete_classes`"""
        return PBSClassicScheduler, PBSExecutorConfig


class AsyncPBSClassicJobExecutor(AsyncBatchSchedulerExecutor):
    """Asynchronous job executor for class PBS schedulers."""

    def get_concrete_classes(self) \
            -> Tuple[Type[BatchScheduler], Type[BatchSchedulerExecutorConfig]]:
        """See :meth:`~.BatchSchedulerExecutor.get_concrete_classes`"""
        return PBSClassicScheduler, PBSExecutorConfig
