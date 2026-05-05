from urllib.parse import urlparse
from enum import Enum, Flag
from pathlib import Path
from typing import Optional, Union

from .job_state import JobState


class URI:
    """A class representing a local or remote file."""

    def __init__(self, urlstring: str) -> None:
        """
        Parameters
        ----------
        urlstring
            A string representation of a URI, such as "http://example.com/file.txt" or "file.txt".
            The precise format of an URI string is defined in
            `RFC3986 <https://datatracker.ietf.org/doc/html/rfc3986.html>`_.
        """
        self.parts = urlparse(urlstring)

    # a __getattr__ solution may be simpler, but doesn't play well with IDEs and
    # is not quite self-documenting
    @property
    def hostname(self) -> Optional[str]:
        """
        Returns
        -------
        Represents the hostname in this URI or `None` if no hostname was specified.
        """
        return self.parts.hostname

    @property
    def port(self) -> Optional[int]:
        """
        Returns
        -------
        Returns the TCP port of this URI or None if a port was not specified.
        """
        return self.parts.port

    @property
    def scheme(self) -> str:
        """
        Returns
        -------
        Returns the URI scheme in this URI or the empty string if no scheme was specified.
        """
        return self.parts.scheme

    @property
    def netloc(self) -> str:
        """
        Returns
        -------
        Returns the network location, which may the host name, the port, and possibly login
        information. If none of these are specified, the empty string is returned.
        """
        return self.parts.netloc

    @property
    def path(self) -> str:
        """
        Returns
        -------
        Returns the path in this URI or an empty string if no path was specified.
        """
        return self.parts.path

    @property
    def params(self) -> str:
        """
        Returns
        -------
        Returns the URI parameters or an empty string if there are no parameters.
        """
        return self.parts.params

    @property
    def query(self) -> str:
        """
        Returns
        -------
        Returns the URI query string or an empty string if no query string was specified.
        """
        return self.parts.query

    @property
    def fragment(self) -> str:
        """
        Returns
        -------
        Returns the fragment in this URI or the empty string if no fragment is specified.
        """
        return self.parts.fragment

    @property
    def username(self) -> Optional[str]:
        """
        Returns
        -------
        Returns the username in this URI if any, or None if there is no username specified.
        """
        return self.parts.username

    @property
    def password(self) -> Optional[str]:
        """
        Returns
        -------
        Returns the password specified in this URI or None if there is no password.
        """
        return self.parts.password

    def __str__(self) -> str:
        """Returns a string representation of this URI."""
        return self.parts.geturl()

    def __eq__(self, other: object) -> bool:
        """
        Tests if the parameter `other` is equal to this `URI`.

        Returns `True` if `other` is a `URI` and if it represents the same
        resource as this `URI`.
        """
        if isinstance(other, URI):
            return self.parts == other.parts
        else:
            return False

    def __hash__(self) -> int:
        """Computes a hash of this object."""
        return hash(self.parts)


class StagingMode(Enum):
    """
    Defines the possible modes in which the staging of a file can be done.

    JobExecutor implementations are not required to support all staging modes. Non-remote executors
    must default to `COPY` if other modes are not implemented. Remote executors must be able to
    handle `CLIENT_TO_CN` and `CLIENT_TO_HN` modes and must default to `CLIENT_TO_CN` if any of
    `COPY`

    The modes `COPY`, `LINK`, and `MOVE` imply that the source and destination are filesystems
    accessible from the machine where the staging is done, which is typically a compute node
    for most batch scheduler executors.

    The modes `CLIENT_TO_HN`, `CLIENT_TO_CN`, and `HN_TO_CN` are relevant when using a multi-hop
    executor configuration, such as when using a PSI/J remote executor in combination with a batch
    scheduler executor. In such cases `CLIENT_TO_HN` indicates that the file should be staged
    from the machine that the client runs on (i.e., where the process that instantiates the remote
    executor runs) to the head node (i.e., the machine that the service runs on), whereas
    `CLIENT_TO_CN` indicates that the file's source is on the client machine and the destination
    is a filesystem accessible to the compute node where the job runs. The mode `HN_TO_CN` stages
    files from/to the head node to/from the compute node where the job runs.
    When running jobs in a single-hop configuration (e.g., directly through a batch scheduler
    executor), `CLIENT_TO_HN`, `CLIENT_TO_CN`, and `HN_TO_CN` have the same effect as `COPY`.
    """

    COPY = 1
    """
    Copies the file to be staged by performing an operation that is equivalent to the familiar
    `cp` command.
    """
    LINK = 2
    """
    Creates a symbolic link instead of copying the contents of files.
    """
    MOVE = 3
    """
    Moves a file instead of copying it. Moving a file can be nearly instantaneous if both the
    source and the destination are on the same filesystem. However, the OS will likely have to
    resort to copying the contents of the file and the removing the source file if the source and
    destination are on different filesystems, so it is unlikely for this mode to be beneficial over
    a `COPY` in such cases.
    """
    CLIENT_TO_HN = 4
    """
    Copies the file from a remote executor client to the head node where the remote executor
    service runs.
    """
    CLIENT_TO_CN = 5
    """
    Copies the file from a remote executor client to the compute node where the job runs.
    """
    HN_TO_CN = 6
    """
    Copies the file from the node where a service runs (typically an HPC "head node") to
    a filesystem accessible to the machine where the job runs (typically an HPC "compute node").
    """


class StageOutFlags(Flag):
    """
    Specifies a set of flags that can be used to alter stage out behavior.

    The flags can be combined using the bitwise or operator (`|`). For example,
    `IF_PRESENT | ON_ERROR`. If none of the state conditions
    (`ON_SUCCESS`, `ON_ERROR`, `ON_CANCEL`) are specified, it is assumed that the file should be
    transferred only when the job executable invocation succeeds, subject to the presence of the
    `IF_PRESENT` flag. That is, `NONE` is equivalent to `ON_SUCCESS`, while `IF_PRESENT` is
    equivalent to `IF_PRESENT | ON_SUCCESS`.
    """

    NONE = 0
    """
    Indicates that no flags are set. This is equivalent to `ON_SUCCESS`.
    """
    IF_PRESENT = 1
    """
    Indicates that a file should only be transferred if it exists. If the file does not exist,
    the stageout operation continues with the next file. If this flag is not set for a given file,
    its absence will result in a stageout error which will cause the job to fail.
    """
    ON_SUCCESS = 2
    """
    Indicates that a file should be transferred when the job succeeds (i.e., its exit code is zero).
    If a job fails or is cancelled, and no other flags are set, the executor will not attempt to
    stage out the file.
    """
    ON_ERROR = 4
    """
    Indicates that a stageout should be performed if the job has failed (i.e., its exit code is
    non-zero).
    """
    ON_CANCEL = 8
    """
    Indicates that a file should be staged out if the job has been canceled.
    """
    ALWAYS = ON_SUCCESS | ON_ERROR | ON_CANCEL
    """
    Indicates that a file should be staged out irrespective of the status of the job.
    """

    def matches(self, state: JobState) -> bool:
        """Checks if the flags match a job state.

        This is a convenience method that checks if a set of flags attached
        to a stage-out directive indicate that the file should be staged out
        given a certain job state. For example, if the job state is `COMPLETED`,
        this method will return `True` if the `ON_SUCCESS` flag is set. This
        method ignores the `IF_PRESENT` flag.

        Parameters
        ----------
        state
            The job state to check against.

        Returns
        -------
            `True` if the file should be stage out and `False` otherwise.
        """
        if not state.final:
            raise ValueError(f'Non-final job state: {state}')
        if state == JobState.COMPLETED:
            return StageOutFlags.ON_SUCCESS in self
        if state == JobState.FAILED:
            return StageOutFlags.ON_ERROR in self
        if state == JobState.CANCELED:
            return StageOutFlags.ON_CANCEL in self
        return False


class StageIn:
    """A class representing a stagein directive."""

    def __init__(self, source: Union[URI, Path, str], target: Union[str, Path],
                 mode: StagingMode = StagingMode.COPY) -> None:
        """
        Parameters
        ----------
        source
            The source location of the stagein. If the source is a string or a :
            class:`~pathlib.Path`, the location refers to a file on a filesystem accessible by the
            process in which PSI/J is running. If the path is relative, it is interpreted to be
            relative to the current working directory of the process in which PSI/J is running and
            normalized to an absolute path. If the source is a :class:`.URI`, it may refer to a
            remote location. Support for remote staging is not guaranteed and depends on the
            implementation of the :class:`~psij.JobExecutor` that the job to which this stagein
            directive belongs is submitted to.
        target
            The target location for the stagein, which can be either a string or a
            :class:`~pathlib.Path`. If the path is relative, it is considered to be relative to the
            job directory. That is, a job can access this file at the location specified by
            `target` if it does not change its working directory from the one it starts in.
        mode
            A staging mode, which indicates how the staging is done. For details, see
            :class:`.StagingMode`.
        """
        if isinstance(source, str):
            source = Path(source)
        if isinstance(source, Path):
            if not source.is_absolute():
                source = source.absolute()
            source = URI(str(source))
        if isinstance(target, str):
            target = Path(target)
        self.source = source
        self.target = target
        self.mode = mode

    def __str__(self) -> str:
        """Returns a string representation of this object."""
        return 'StageIn[%s -> %s, %s]' % (self.source, self.target, self.mode)

    def __eq__(self, other: object) -> bool:
        """Compares `other` to this object."""
        if isinstance(other, StageIn):
            return (self.source == other.source and self.target == other.target
                    and self.mode == other.mode)
        else:
            return False

    def __hash__(self) -> int:
        """Computes a hash of this object."""
        return (hash(self.source) << 16) + (hash(self.target) << 8) + hash(self.mode)


def _normalize_flags(flags: StageOutFlags) -> StageOutFlags:
    if (flags & StageOutFlags.ALWAYS).value == 0:
        return flags | StageOutFlags.ON_SUCCESS
    else:
        return flags


class StageOut:
    """A class encapsulating a stageout directive."""

    def __init__(self, source: Union[str, Path], target: Union[str, Path, URI],
                 flags: StageOutFlags = StageOutFlags.ON_SUCCESS,
                 mode: StagingMode = StagingMode.COPY):
        """
        Parameters
        ----------
        source
            The source location for the stagein, which can be either a string or a
            :class:`~pathlib.Path`. If the path is relative, it is considered to be relative to the
            job directory.
        target
            The target location of the stageout. If the target is a string or a
            :class:`~pathlib.Path`, the location refers to a file on a filesystem accessible by the
            process in which PSI/J is running. If the path is relative, it is interpreted to be
            relative to the current working directory of the process in which PSI/J is running and
            normalized to an absolute path. If the target is a :class:`.URI`, it may refer to a
            remote location. Support for remote staging is not guaranteed and depends on the
            implementation of the :class:`~psij.JobExecutor` that the job to which this stageout
            directive belongs is submitted to.
        flags
            A set of flags specifying the conditions under which the stageout should occur. For
            details, see :class:`.StageOutFlags`.
        mode
            A staging mode, which indicates how the staging is done. For details, see
            :class:`.StagingMode`.
        """
        if isinstance(source, str):
            source = Path(source)
        if isinstance(target, str):
            target = Path(target)
        if isinstance(target, Path):
            if not target.is_absolute():
                target = target.absolute()
            target = URI(str(target))

        self.source = source
        self.target = target
        self.flags = flags
        self.mode = mode

    @property
    def flags(self) -> StageOutFlags:
        """
        A set of flags specifying the conditions under which the stageout should occur.

        For details, see :class:`.StageOutFlags`.
        """
        return self._flags

    @flags.setter
    def flags(self, flags: StageOutFlags) -> None:
        self._flags = _normalize_flags(flags)

    def __str__(self) -> str:
        """Returns a string representation of this object."""
        return 'StageOut[%s -> %s, %s, %s]' % (self.source, self.target, self.flags, self.mode)

    def __eq__(self, other: object) -> bool:
        """Compares `other` to this object."""
        if isinstance(other, StageOut):
            return (self.source == other.source and self.target == other.target
                    and self.mode == other.mode and self.flags == other.flags)
        else:
            return False

    def __hash__(self) -> int:
        """Computes a hash of this object."""
        return ((hash(self.source) << 24) + (hash(self.target) << 16) + (hash(self.mode) << 8)
                + hash(self.flags))
