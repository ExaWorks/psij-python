from datetime import timedelta
from typing import Optional, Dict


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
