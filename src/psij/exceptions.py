"""A collection of exceptions used by PSI/J."""
from datetime import timedelta
from typing import Optional, List


class InvalidJobException(Exception):
    """An exception describing a problem with a job specification."""

    def __init__(self, message: str, exception: Optional[Exception] = None) -> None:
        """
        :param message: A message associated with this exception. This is a descriptive message
            that is sufficiently clear to be presented to an end-user.
        :param exception: An optional underlying exception that can potentially be used for
            debugging purposes, but which should not, in general, be presented to an end-user.
        """
        self.message = message
        self.exception = exception


class BackendException(Exception):
    """
    An exception representing job submission issues.

    This exception is thrown when job management calls of instances of :class:`~psij.JobExecutor`
    fail for reasons that cannot generally be corrected with changes to the job. Examples include
    a queuing system being down, a network connection not being present, etc.

    """

    def __init__(self, message: str, exception: Optional[Exception] = None,
                 transient: bool = False) -> None:
        """
        :param message: The message associated with this exception. This is a descriptive message
            that is sufficiently clear to be presented to an end-user.
        :param exception: An optional underlying exception that can potentially be used for
            debugging purposes, but which should not, in general, be presented to an end-user.
        :param transient: `True` if the underlying condition that triggered this exception is
            transient. Jobs that cannot be submitted due to a transient exceptional condition have
            a chance of being successfully re-submitted at a later time, which is a suggestion to
            client code that it could re-attempt the operation that triggered this exception.
            However, the exact chances of success depend on many factors and are not guaranteed in
            any particular case. For example, a DNS resolution failure while attempting to connect
            to a remote service is a transient error since it can be reasonably assumed that DNS
            resolution is a persistent feature of an Internet-connected network. By contrast, an
            authentication failure due to an invalid username/password combination would not be a
            transient failure. While it may be possible for a temporary defect in a service to
            cause such a failure, under normal operating conditions such an error would persist
            across subsequent re-tries until correct credentials are used.
        """
        self.message = message
        self.exception = exception
        self.transient = transient


class SubmitException(BackendException):
    """
    An exception representing job submission issues.

    This exception is thrown when the :func:`~psij.JobExecutor.submit` call fails for
    a reason that is independent of the job that is being submitted. It is a specialized version
    of :class:`~.BackendException`
    """

    pass


class ExecutorException(Exception):
    """
    Exception representing executor initialization problems.

    This exception can be thrown when an executor is initialized, such as
    through :func:`~psij.JobExecutor.get_instance`.
    """

    def __init__(self, message: str, exception: Optional[Exception] = None):
        """
        :param message: A message associated with this exception. This is a descriptive message
            that is sufficiently clear to be presented to an end-user.
        :param exception: An optional underlying exception that can potentially be used for
            debugging purposes, but which should not, in general, be presented to an end-user.
        """
        self.message = message
        self.exception = exception


class JobException(Exception):
    """
    Raised by some methods when a job completes in a failure.

    This class also allows for exceptions encountered during stage-out and
    cleanup to be chained and reported to the user.
    """

    def __init__(self, message: Optional[str], exit_code: Optional[int] = None) -> None:
        """
        :param message: A message associated with this exception. This is a descriptive message
            that is sufficiently clear to be presented to an end-user.
        :param exit_code: An optional exit code, if available from the job.
        """
        self.message = message
        self.exit_code = exit_code
        self._others: Optional[List[Exception]] = None

    def add_exception(self, ex: Exception) -> None:
        """
        Adds a staging/cleanup exception to this `JobException`.

        Parameters
        ----------
        ex
            The exception to add.
        """
        if self._others is None:
            self._others = [ex]
        else:
            self._others.append(ex)

    def __str__(self) -> str:
        """Converts this exception to a string."""
        if self.message is None:
            s = f'Job failed with exit code {self.exit_code}'
        else:
            s = self.message

        if self._others is not None:
            s += '. In addition, the following error(s) have occurred during staging/cleanup:\n'
            for ex in self._others:
                s += str(ex)
                s += '\n'

        return s


class ValidityError(Exception):
    """
    Raised when a requested session validity cannot be met by a server.

    See :meth:`~.JobExecutor.disconnect`.
    """

    def __init__(self, requested: timedelta, max: timedelta) -> None:
        """
        Parameters
        ----------
        requested
            The validity that was requested.
        max
            The maximum validity allowed by the server.
        """
        self.requested = requested
        self.max = max

    def __str__(self) -> str:
        """Returns a human-readable representation of this exception."""
        return f'Maximum validity exceeded: requested {self.requested}, max: {self.max}'
