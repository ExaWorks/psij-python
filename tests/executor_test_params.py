from typing import Optional


class ExecutorTestParams:
    def __init__(self, spec: str) -> None:
        spec_l = spec.split(':')
        self.executor = spec_l[0]
        if len(spec_l) > 1:
            self.launcher = spec_l[1]  # type: Optional[str]
        else:
            self.launcher = None
        if len(spec_l) == 3:
            self.url = spec_l[2]  # type: Optional[str]
        else:
            self.url = None

    def __str__(self) -> str:
        if self.launcher is not None:
            if self.url is not None:
                return '{}:{}:{}'.format(self.executor, self.launcher, self.url)
            else:
                return '{}:{}'.format(self.executor, self.launcher)
        else:
            if self.url is not None:
                return '{}::{}'.format(self.executor, self.url)
            else:
                return '{}'.format(self.executor)

    def __repr__(self) -> str:
        return self.__str__()
