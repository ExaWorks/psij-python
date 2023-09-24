import re
from datetime import timedelta
from typing import Optional, Dict

from typeguard import check_argument_types


_WALLTIME_FMT_ERROR = 'Unknown walltime format: %s. Accepted formats are hh:mm:ss, ' \
                      'hh:mm, mm, or n\\s*[h|m|s].'


class JobAttributes(object):
    """A class containing ancillary job information that describes how a job is to be run."""

    def __init__(self, duration: timedelta = timedelta(minutes=10),
                 queue_name: Optional[str] = None, project_name: Optional[str] = None,
                 reservation_id: Optional[str] = None,
                 custom_attributes: Optional[Dict[str, object]] = None) -> None:
        """
        Constructs a `JobAttributes` instance while allowing its various fields to be initialized.

        :param duration: Specifies the duration (walltime) of the job. A job whose execution
            exceeds its walltime can be terminated forcefully.
        :param queue_name: If a backend supports multiple queues, this parameter can be used to
            instruct the backend to send this job to a particular queue.
        :param project_name: If a backend supports multiple projects for billing purposes, setting
            this attribute instructs the backend to bill the indicated project for the resources
            consumed by this job.
        :param reservation_id: Allows specifying an advanced reservation ID. Advanced reservations
            enable the pre-allocation of a set of resources/compute nodes for a certain duration
            such that jobs can be run immediately, without waiting in the queue for resources to
            become available.
        :param custom_attributes: Specifies a dictionary of custom attributes. Implementations of
            :class:`~psij.JobExecutor` define and are responsible for interpreting custom
            attributes.
        """
        assert check_argument_types()

        self.duration = duration
        self.queue_name = queue_name
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
        return 'JobAttributes(duration={}, queue_name={}, project_name={}, reservation_id={}, ' \
               'custom_attributes={})'.format(self.duration, self.queue_name, self.project_name,
                                              self.reservation_id, self._custom_attributes)

    def __eq__(self, o: object) -> bool:
        """
        Tests if this JobAttributes object is equal to another object.

        The objects are equal if all their properties are equal.
        """
        if not isinstance(o, JobAttributes):
            return False

        for prop_name in ['duration', 'queue_name', 'project_name', 'reservation_id',
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
