"""This module contains the core classes of the launchers infrastructure."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict

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
        Base constructors for launchers.

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

    @abstractmethod
    def is_launcher_failure(self, output: str) -> bool:
        """
        Determines whether the launcher invocation output contains a launcher failure or not.

        Parameters
        ----------
        output
            The output (combined stdout/stderr) from an invocation of the launcher command

        Returns
        -------
        Returns `True` if the output of the launcher indicates that it has exited with a
        non-zero exit code due to an error occurring in the launcher.

        """
        pass

    @abstractmethod
    def get_launcher_failure_message(self, output: str) -> str:
        """
        Extracts the launcher error message from the output of this launcher's invocation.

        It is understood that the output is such that
        :func:`~psij.launcher.Launcher.is_launcher_failure` returns `True` on it.

        Parameters
        ----------
        output
            The output (combined stdout/stderr) from an invocation of the launcher command.

        Returns
        -------
        A string representing the part of the launcher output that describes the launcher
        error.
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
