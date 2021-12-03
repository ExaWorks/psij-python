import re
from typing import Optional, Dict


class ExecutorTestParams:
    """A class holding executor, launcher, url pairs."""

    def __init__(self, spec: str, custom_attributes: Optional[Dict[str, object]] = None) -> None:
        """
        Construct a new instance.

        Parameters
        ----------
        spec:
            A string in the format "<executor>[:<launcher>[:<url>]]". If only the executor and the
            url are specified, the string should be formatted as "<executor>::<url>".
        """
        spec_l = re.split(':', spec, maxsplit=2)
        self.executor = spec_l[0]
        if len(spec_l) > 1:
            self.launcher = spec_l[1]  # type: Optional[str]
        else:
            self.launcher = None
        if len(spec_l) == 3:
            self.url = spec_l[2]  # type: Optional[str]
        else:
            self.url = None

        self.custom_attributes = custom_attributes

    def __repr__(self) -> str:
        """Returns a string representation of this object."""
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
