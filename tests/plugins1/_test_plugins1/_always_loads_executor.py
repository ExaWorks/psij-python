from typing import List, Optional

from psij import JobExecutor, Job, JobExecutorConfig


class AlwaysLoadsExecutor(JobExecutor):
    """A test job executor that is guaranteed to always load."""

    def __init__(self, url: str, config: Optional[JobExecutorConfig]):
        """See :func:`~JobExecutor.__init__`."""
        super().__init__(None, JobExecutorConfig())

    def submit(self, job: Job) -> None:
        """See :func:`~JobExecutor.submit`."""
        pass

    def cancel(self, job: Job) -> None:
        """See :func:`~JobExecutor.cancel`."""
        pass

    def list(self) -> List[str]:
        """See :func:`~JobExecutor.list`."""
        pass

    def attach(self, job: Job, native_id: str) -> None:
        """See :func:`~JobExecutor.attach`."""
        pass
