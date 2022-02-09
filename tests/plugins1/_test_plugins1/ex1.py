from typing import List, Optional

from psij import JobExecutor, Job, JobExecutorConfig


class _Executor1(JobExecutor):
    def __init__(self, url: Optional[str] = None, config: Optional[JobExecutorConfig] = None):
        super().__init__(url, JobExecutorConfig())

    def submit(self, job: Job) -> None:
        pass

    def cancel(self, job: Job) -> None:
        pass

    def list(self) -> List[str]:
        pass

    def attach(self, job: Job, native_id: str) -> None:
        pass
