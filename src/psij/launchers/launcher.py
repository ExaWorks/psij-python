"""This module contains the core classes of the launchers infrastructure."""

from abc import ABC, abstractmethod
from typing import Optional, List, Type, Dict

from psij.job_executor_config import JobExecutorConfig
from psij.job import Job


class Launcher(ABC):
    """An abstract base class for all launchers."""

    _launchers = {}  # type: Dict[str, Type[Launcher]]

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
            Returns `True` if the output

        """
        pass

    @abstractmethod
    def get_launcher_failure_message(self, output: str) -> str:
        """
        Extracts the launcher error message from the output of this launcher's invocation.

        It is understood that the output is such that
        :func:`~psij.laucnhers.launcher.Launcher.is_launcher_failure` returns `True` on it.

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
    def get_instance(name: str, config: Optional[JobExecutorConfig] = None) -> 'Launcher':
        """
        Returns an instance of a launcher optionally configured using a certain configuration.

        The returned instance may or may not be a singleton object.

        :param name: The name of the launcher to return an instance of.
        :param config: An optional configuration.
        :return: A launcher instance.
        """
        if name not in Launcher._launchers:
            raise ValueError('No such launcher: "{}"'.format(name))
        lcls = Launcher._launchers[name]
        return lcls(config=config)

    @staticmethod
    def register_launcher(lcls: Type['Launcher']) -> None:
        """
        Registers a launcher class.

        The registered class cang then be instantiated using
            :func:`~psij.Launcher.get_instance`.

        :param lcls: The launcher class to register.
        """
        if not hasattr(lcls, '_NAME_'):
            raise ValueError('Class is missing the launcher name attribute, "_NAME_"')
        name = getattr(lcls, '_NAME_')
        Launcher._launchers[name] = lcls
