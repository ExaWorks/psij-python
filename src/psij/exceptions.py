"""A collection of exceptions used by PSI/J."""
from typing import Optional


class InvalidJobException(Exception):
    """An exception describing a problem with a job specification."""

    def __init__(self, message: str, exception: Optional[Exception] = None) -> None:
        """
        :param message: see the :attr:`message` property
        :param exception: see the :attr:`exception` property
        """
        self.message = message
        """
        Retrieves the message associated with this exception. This is a descriptive message that is
        sufficiently clear to be presented to an end-user.
        """
        self.exception = exception
        """
        Returns an optional underlying exception that can potentially be used for debugging
        purposes, but which should not, in general, be presented to an end-user.
        """


class SubmitException(Exception):
    """
    An exception representing job submission issues.

    This exception is thrown when the :func:`~psij.JobExecutor.submit` call fails for
    a reason that is independent of the job that is being submitted.
    """

    def __init__(self, message: str, exception: Optional[Exception] = None,
                 transient: bool = False) -> None:
        """
        :param message: see :attr:`message`
        :param exception: see :attr:`exception`
        :param transient: see :attr:`transient`
        """
        self.message = message
        """
        Retrieves the message associated with this exception. This is a descriptive message
        that is sufficiently clear to be presented to an end-user.
        """
        self.exception = exception
        """
        Returns an optional underlying exception that can potentially be used for debugging
        purposes, but which should not, in general, be presented to an end-user.
        """
        self.transient = transient
        """
        Returns `True` if the underlying condition that triggered this exception is transient.
        Jobs that cannot be submitted due to a transient exceptional condition have chance of being
        successfully re-submitted at a later time, which is a suggestion to client code that it
        could re-attempt the operation that triggered this exception. However, the exact chances of
        success depend on many factors and are not guaranteed in any particular case. For example,
        a DNS resolution failure while attempting to connect to a remote service is a transient
        error since it can be reasonably assumed that DNS resolution is a persistent feature of an
        Internet-connected network. By contrast, an authentication failure due to an invalid
        username/password combination would not be a transient failure. While it may be possible
        for a temporary defect in a service to cause such a failure, under normal operating
        conditions such an error would persist across subsequent re-tries until correct credentials
        are used.
        """
