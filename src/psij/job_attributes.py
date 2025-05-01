import logging
import re
from datetime import timedelta
from typing import Optional, Dict

from typeguard import typechecked


logger = logging.getLogger(__name__)


_WALLTIME_FMT_ERROR = 'Unknown walltime format: %s. Accepted formats are hh:mm:ss, ' \
                      'hh:mm, mm, or n\\s*[h|m|s].'


class JobAttributes(object):
    """A class containing ancillary job information that describes how a job is to be run."""

    @typechecked
    def __init__(self, duration: timedelta = timedelta(minutes=10),
                 queue_name: Optional[str] = None, account: Optional[str] = None,
                 reservation_id: Optional[str] = None,
                 custom_attributes: Optional[Dict[str, object]] = None,
                 project_name: Optional[str] = None) -> None:
        """
        :param duration: Specifies the duration (walltime) of the job. A job whose execution
            exceeds its walltime can be terminated forcefully.
        :param queue_name: If a backend supports multiple queues, this parameter can be used to
            instruct the backend to send this job to a particular queue.
        :param account: An account to use for billing purposes. Please note that the executor
            implementation (or batch scheduler) may use a different term for the option used for
            accounting/billing purposes, such as `project`. However, scheduler must map this
            attribute to the accounting/billing option in the underlying execution mechanism.
        :param reservation_id: Allows specifying an advanced reservation ID. Advanced reservations
            enable the pre-allocation of a set of resources/compute nodes for a certain duration
            such that jobs can be run immediately, without waiting in the queue for resources to
            become available.
        :param custom_attributes: Specifies a dictionary of custom attributes. Implementations of
            :class:`~psij.JobExecutor` define and are responsible for interpreting custom
            attributes.
            The typical usage scenario for custom attributes is to pass information to the executor
            or underlying job execution mechanism that cannot otherwise be passed using the classes
            and properties provided by PSI/J. A specific example is that of the subclasses of
            :class:`~psij.executors.batch.batch_scheduler_executor.BatchSchedulerExecutor`, which
            look for custom attributes prefixed with their name and a dot (e.g., `slurm.constraint`,
            `pbs.c`, `lsf.core_isolation`) and translate them into the corresponding batch
            scheduler directives (e.g., `#SLURM --constraint=...`, `#PBS -c ...`,
            `#BSUB -core_isolation ...`).
        :param project_name: Deprecated. Please use the `account` attribute.

        All constructor parameters are accessible as properties.
        """
        self.account = account
        self.duration = duration
        self.queue_name = queue_name
        if project_name is not None:
            self.project_name = project_name
        self.reservation_id = reservation_id
        self._custom_attributes = custom_attributes

    def set_custom_attribute(self, name: str, value: object) -> None:
        """Sets a custom attribute."""
        if self._custom_attributes is None:
            self._custom_attributes = {}
        self._custom_attributes[name] = value

    def get_custom_attribute(self, name: str) -> Optional[object]:
        """Retrieves the value of a custom attribute."""
        if self._custom_attributes is None:
            return None
        if name not in self._custom_attributes:
            return None
        return self._custom_attributes[name]

    @property
    def custom_attributes(self) -> Optional[Dict[str, object]]:
        """Returns a dictionary with the custom attributes."""
        return self._custom_attributes

    @custom_attributes.setter
    def custom_attributes(self, attrs: Optional[Dict[str, object]]) -> None:
        """
        Sets all custom attributes from the given dictionary.

        Existing custom attributes defined on this instance of `JobAttributes`
        are removed.

        Parameters
        ----------
        attrs
            A dictionary with the custom attributes to set.
        """
        self._custom_attributes = attrs

    def __repr__(self) -> str:
        """Returns a string representation of this object."""
        return 'JobAttributes(duration={}, queue_name={}, account={}, reservation_id={}, ' \
               'custom_attributes={})'.format(self.duration, self.queue_name, self.account,
                                              self.reservation_id, self._custom_attributes)

    def __eq__(self, o: object) -> bool:
        """
        Tests if this JobAttributes object is equal to another object.

        The objects are equal if all their properties are equal.
        """
        if not isinstance(o, JobAttributes):
            return False

        for prop_name in ['duration', 'queue_name', 'account', 'reservation_id',
                          'custom_attributes']:
            if getattr(self, prop_name) != getattr(o, prop_name):
                return False

        return True

    @staticmethod
    def parse_walltime(walltime: str) -> timedelta:
        r"""
        Parses a walltime string into a :class:`~datetime.timedelta`.

        The accepted walltime strings formats are:
        * hh:mm:ss
        * hh:mm
        * mm
        * n\s*[y|M|d|h|m\s]

        Parameters
        ----------
        walltime
            A string in one of the above formats representing a time duration

        Returns
        -------
        A :class:`~datetime.timedelta` representing the same time duration as the ``walltime``
        parameter.
        """
        if ':' in walltime:
            parts = walltime.split(':')
            seconds = 0
            if len(parts) == 3:
                seconds = int(parts[2])
            if len(parts) <= 3:
                return timedelta(hours=int(parts[0]), minutes=int(parts[1]), seconds=seconds)
            else:
                raise ValueError(_WALLTIME_FMT_ERROR % walltime)
        if walltime.isdigit():
            return timedelta(minutes=int(walltime))
        m = re.search(r'(\d+)\s*([hms])', walltime)
        if m:
            digits = m.group(1)
            unit = m.group(2)
            val = int(digits)
            if unit == 'h':
                return timedelta(hours=val)
            elif unit == 'm':
                return timedelta(minutes=val)
            elif unit == 's':
                return timedelta(seconds=val)
        raise ValueError(_WALLTIME_FMT_ERROR % walltime)

    @property
    def project_name(self) -> Optional[str]:
        """Deprecated. Please use the `account` attribute."""
        return self.account

    @project_name.setter
    def project_name(self, project_name: Optional[str]) -> None:
        if project_name is not None:
            logger.warning('The "project_name" attribute is deprecated. Please use the "account" '
                           'attribute instead.')
        self.account = project_name
