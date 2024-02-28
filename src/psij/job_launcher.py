"""This module contains the core classes of the launchers infrastructure."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Set

from psij.descriptor import Descriptor, _VersionEntry
from psij._plugins import _register_plugin, _get_plugin_class, _print_plugin_status
from psij.job_executor_config import JobExecutorConfig
from psij.job import Job


class Launcher(ABC):
    """An abstract base class for all launchers."""

    _launchers: Dict[str, List[_VersionEntry['Launcher']]] = {}
    DEFAULT_LAUNCHER_NAME = 'single'

    def __init__(self, config: Optional[JobExecutorConfig] = None) -> None:
        """
        :param config: An optional configuration. If not specified,
            :attr:`~psij.JobExecutorConfig.DEFAULT` is used.
        """
        if config is None:
            config = JobExecutorConfig.DEFAULT
        self.config = config

    @abstractmethod
    def get_launch_command(self, job: Job) -> List[str]:
        """
        Constructs a command to launch a job given a job specification.

        :param job: The job to launch.
        :return: A list of strings representing the launch command and all of its arguments.
        """
        pass

    @staticmethod
    def get_instance(name: str, version_constraint: Optional[str] = None,
                     config: Optional[JobExecutorConfig] = None) -> 'Launcher':
        """
        Returns an instance of a launcher optionally configured using a certain configuration.

        The returned instance may or may not be a singleton object.

        :param name: The name of the launcher to return an instance of.
        :param config: An optional configuration.
        :return: A launcher instance.
        """
        selected = _get_plugin_class(name, version_constraint, 'launcher', Launcher._launchers)

        assert selected.ecls is not None
        assert issubclass(selected.ecls, Launcher)
        setattr(selected.ecls, '_NAME_', name)
        setattr(selected.ecls, '_VERSION_', selected.version)
        instance = selected.ecls(config=config)
        return instance

    @staticmethod
    def register_launcher(desc: Descriptor, root: str) -> None:
        """
        Registers a launcher class.

        The registered class can then be instantiated using :func:`~psij.Launcher.get_instance`.

        Parameters
        ----------
        desc
            A :class:`~psij.descriptor.Descriptor` with information about the launcher to
            register.
        root
            A filesystem path under which the implementation of the launcher is to be loaded from.
            Launchers from other locations, even if under the correct package, will not be
            registered by this method. If a launcher implementation is only available under a
            different root path, this method will throw an exception.
        """
        _register_plugin(desc, root, 'launcher', Launcher._launchers)

    @staticmethod
    def _print_plugin_status() -> None:
        _print_plugin_status(Launcher._launchers, 'launcher')

    @staticmethod
    def get_launcher_names() -> Set[str]:
        """
        Returns a set of registered launcher names.

        Names returned by this method can be passed to :func:`~psij.Launcher.get_instance` as
        the `name` parameter.

        Returns
        -------
        A set of launcher names corresponding to the known executors.
        """
        return set(Launcher._launchers.keys())
