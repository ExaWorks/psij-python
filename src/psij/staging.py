from urllib.parse import urlparse
from enum import Enum, Flag
from pathlib import Path
from typing import Optional, Union


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
        """Returns a string representation of this URL."""
        return self.parts.geturl()


class StagingMode(Enum):
    """
    Defines the possible modes in which the staging of a file can be done.

    JobExecutor implementations are not required to support all staging modes, but must default
    to `COPY` if other modes are not implemented. Furthermore, modes different from `COPY` may only
    make sense when staging is done locally.
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
    a `COPY`.
    """


class StageOutFlags(Flag):
    """
    Specifies a set of flags that can be used to alter stage out behavior.

    The flags can be combined using the bitwise or operator (`|`). For example,
    `IF_PRESENT | ON_ERROR`. If none of the state conditions
    (`ON_SUCCESS`, `ON_ERROR`, `ON_CANCEL`) are specified, it is assumed that the file should be
    transferred in all cases, subject to the presence of the `IF_PRESENT` flag. That is,
    `NONE` is equivalent to `ALWAYS` or `ON_SUCCESS | ON_ERROR | ON_CANCEL`, while
    `IF_PRESENT` is equivalent to `IF_PRESENT | ALWAYS`.
    """

    NONE = 0
    """
    Indicates that no flags are set. This is equivalent to `ALWAYS`.
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
            source = URI(source)
        if isinstance(source, Path):
            source = URI(str(source))
        if isinstance(target, str):
            target = Path(target)
        self.source = source
        self.target = target
        self.mode = mode


def _normalize_flags(flags: StageOutFlags) -> StageOutFlags:
    if (flags & StageOutFlags.ALWAYS).value == 0:
        return flags | StageOutFlags.ALWAYS
    else:
        return flags


class StageOut:
    """A class encapsulating a stageout directive."""

    def __init__(self, source: Union[str, Path], target: Union[str, Path, URI],
                 flags: StageOutFlags = StageOutFlags.ALWAYS,
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
            target = URI(target)
        if isinstance(target, Path):
            target = URI(str(target))

        print(target.parts)
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
