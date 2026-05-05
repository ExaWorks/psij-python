import logging
from abc import ABC
from packaging.version import Version
from threading import RLock
from typing import Optional, Dict, cast, List

# This import ensures that all descriptors are loaded
from psij.base_job import BaseJob
from psij._plugins import _get_plugin_class
from psij.descriptor import _VersionEntry
from psij.exceptions import InvalidJobException
from psij.resource_spec import ResourceSpecV1
from psij.job_spec import JobSpec
from psij.job_state import JobState
from psij.job_executor_config import JobExecutorConfig
from psij.job_launcher import Launcher


logger = logging.getLogger(__name__)


_DEFAULT_RESOURCES = ResourceSpecV1()


class BaseExecutor(ABC):
    """A base class for job executors, both synchronous and asynchronous."""

    def __init__(self, url: Optional[str] = None,
                 config: Optional[JobExecutorConfig] = None):
        """
        :param url: The URL is a string that a `JobExecutor` implementation can interpret as the
            location of a backend.
        :param config: An configuration specific to each `JobExecutor` implementation. This
            parameter is marked as optional such that concrete `JobExecutor` classes can be
            instantiated with no `config` parameter. However, concrete `JobExecutor` classes
            must pass a default configuration up the inheritance tree and ensure that the
            `config` parameter of the ABC constructor is non-null.
        """
        self.url = url
        assert config
        self.config = config
        self._launchers_lock = RLock()
        self._launchers: Dict[str, Launcher] = {}

    @property
    def name(self) -> str:
        """Returns the name of this executor."""
        # The _NAME_ class attribute is set by the instantiation mechanism. This is only done to
        # avoid name duplication/matching issues (name defined by the descriptor vs. name defined
        # statically by a pre-set _NAME_attribute), but is not otherwise necessary to do so. In
        # other words, one could very well return a static value here and ensure that the
        # descriptor has the same name for this class.
        return cast(str, getattr(self.__class__, '_NAME_'))

    @property
    def version(self) -> Version:
        """Returns the version of this executor."""
        return cast(Version, getattr(self.__class__, '_VERSION_'))

    def _check_job(self, job: BaseJob) -> JobSpec:
        """
        Checks a job for consistency and correctness.

        Verifies that various aspects of the job are correctly specified. This includes precisely
        the following checks:
        * the job has a non-null specification
        * job.spec.environment is a Dict[str, [str | int]]

        While this method makes a fair attempt at ensuring the validity of the job, it makes no
        such guarantees. Specifically, if an executor implementation requires checks not listed
        above, it should implement them explicitly.

        These checks are meant to trigger common runtime type errors somewhat early and with clear
        error messages. In production software, these checks can be disabled by invoking Python
        with one of the optimization flags (`-O` or `-OO`).

        Upon completion, this method sets the :attr:`~psij.Job.executor` attribute of the job and
        returns the job specification.

        Parameters
        ----------
        job
            The job to validate

        Returns
        -------
            A non-null job specification
        """
        if job.status.state != JobState.NEW:
            raise InvalidJobException('Job must be in NEW state')
        spec = job.spec
        if not spec:
            raise InvalidJobException('Missing specification')
        if not spec.resources:
            spec.resources = _DEFAULT_RESOURCES

        if __debug__:
            if spec.environment is not None:
                for k, v in spec.environment.items():
                    if not isinstance(k, str):
                        raise TypeError('environment key "%s" is not a string (%s)'
                                        % (k, type(k).__name__))
                    if not isinstance(v, (str, int)):
                        raise TypeError('environment value for key "%s" must be string '
                                        'or int type (%s)' % (k, type(v).__name__))

        if job.executor is not None:
            raise InvalidJobException('Job is already associated with an executor')
        job.executor = self
        return spec

    @staticmethod
    def _get_instance(name: str, version_constraint: Optional[str], url: Optional[str],
                      config: Optional[JobExecutorConfig], _async: bool,
                      map: Dict[str, List[_VersionEntry['BaseExecutor']]]) -> 'BaseExecutor':
        type = 'async-executor' if _async else 'executor'
        selected = _get_plugin_class(name, version_constraint, type, map)

        assert selected.ecls is not None
        assert issubclass(selected.ecls, BaseExecutor)
        setattr(selected.ecls, '_NAME_', name)
        setattr(selected.ecls, '_VERSION_', selected.version)
        instance = selected.ecls(url=url, config=config)
        return instance

    def _get_launcher(self, name: str, version_constraint: Optional[str] = None) -> Launcher:
        with self._launchers_lock:
            if name not in self._launchers:
                self._launchers[name] = Launcher.get_instance(name,
                                                              version_constraint=version_constraint,
                                                              config=self.config)
            return self._launchers[name]
