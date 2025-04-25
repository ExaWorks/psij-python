from typing import Optional, List, Dict
from datetime import datetime


class ResourceInfo(object):
    """Class to resource information about a job."""

    def __init__(self, hostname: str, cores: int):
        """
        Initialize the ResourceInfo object.

        :param name: Name of the resource.
        :param cores: Number of cores allocated for the job.
        """
        self.hostname = hostname
        self.cores = cores

    def __repr__(self) -> str:
        """Return a string representation of the ResourceInfo instance."""
        return f"ResourceInfo(name={self.hostname}, cores={self.cores})"


class JobInfo(object):
    """Class to the information about a job."""

    def __init__(self, wall_time: Optional[int] = None,
                 cpu_time: Optional[int] = None,
                 submission_time: Optional[datetime] = None,
                 dispatch_time: Optional[datetime] = None,
                 resources: Optional[List[Dict[str, str | int]]] = None,
                 owner: Optional[str] = None, submit_host: Optional[str] = None):
        """
        Initialize the JobInfo object.

        :param wall_time: Wall time of the job in seconds.
        :param cpu_time: CPU time of the job in seconds.
        :param submission_time: Time when the job was submitted.
        :param dispatch_time: Time when the job was running.
        :param resources: Resource information about the job.
        :param owner: Owner of the job.
        """
        self.wall_time = wall_time
        self.cpu_time = cpu_time
        self.submission_time = submission_time
        self.dispatch_time = dispatch_time
        self.resourcelist = resources
        self.owner = owner
        self.submit_host = submit_host

    def __repr__(self) -> str:
        """Return a string representation of the JobInfo instance."""
        return f"JobInfo(wall_time={self.wall_time}, cpu_time={self.cpu_time}, " \
               f"submission_time={self.submission_time}, dispatch_time={self.dispatch_time}, " \
               f"resourcelist={self.resourcelist}, owner={self.owner})"
