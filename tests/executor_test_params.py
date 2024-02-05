import re
from typing import Optional, Dict


class ExecutorTestParams:
    """A class holding executor, launcher, url pairs."""

    def __init__(self, spec: str, queue_name: Optional[str] = None,
                 project_name: Optional[str] = None,
                 custom_attributes_raw: Optional[Dict[str, Dict[str, object]]] = None) \
            -> None:
        """
        Construct a new instance.

        Parameters
        ----------
        spec
            A string in the format "<executor>[:<launcher>[:<url>]]". If only the executor and the
            url are specified, the string should be formatted as "<executor>::<url>".
        queue_name
            An optional queue to submit the job to
        project_name
            An optional project name to associate the job with
        custom_attributes
        """
        spec_l = re.split(':', spec, maxsplit=2)
        self.executor = spec_l[0]
        if len(spec_l) > 1:
            self.launcher: Optional[str] = spec_l[1]
        else:
            self.launcher = None
        if len(spec_l) == 3:
            self.url: Optional[str] = spec_l[2]
        else:
            self.url = None

        self.queue_name = queue_name
        self.project_name = project_name
        self.custom_attributes_raw = custom_attributes_raw
        self.custom_attributes: Dict[str, object] = {}

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
