"""This module contains a noop test :class:`~psij.JobExecutor`."""
# flake8: noqa
from typing import List, Optional

import does_not_exist  # type: ignore

from psij import JobExecutor, JobExecutorConfig, Job


class __NeverLoadsExecutor(JobExecutor):
    """A job executor that is guaranteed to not load."""

    def __init__(self, url: str, config: Optional[JobExecutorConfig]):
        super().__init__(None, JobExecutorConfig())

    def submit(self, job: Job) -> None:
        pass

    def cancel(self, job: Job) -> None:
        pass

    def list(self) -> List[str]:
        pass

    def attach(self, job: Job, native_id: str) -> None:
        pass
