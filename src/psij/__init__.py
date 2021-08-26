"""The package containing the jobs module of this PSI implementation."""

import importlib
import logging
import os
import pkgutil
import sys
from typing import Callable, Type, TypeVar

from .exceptions import SubmitException, InvalidJobException, UnreachableStateException
from .job import Job, JobStatusCallback
from .job_attributes import JobAttributes
from .job_executor import JobExecutor
from .job_executor_config import JobExecutorConfig
from .job_spec import JobSpec
from .job_state import JobState
from .job_status import JobStatus
from .launchers.launcher import Launcher
from .resource_spec import ResourceSpec, ResourceSpecV1


__all__ = [
    'JobExecutor', 'JobExecutorConfig', 'Job', 'JobStatusCallback', 'JobSpec', 'JobAttributes',
    'JobStatus', 'JobState', 'ResourceSpec', 'ResourceSpecV1', 'Launcher', 'SubmitException',
    'InvalidJobException', 'UnreachableStateException'
]

logger = logging.getLogger(__name__)

T = TypeVar('T')


class _PluginType:
    def __init__(self, name: str, registration_method: Callable[[Type[T]], None]):
        self.name = name
        self.registration_method = registration_method
        self.package = ['psij', name]


TYPES = [_PluginType('executors', JobExecutor.register_executor),
         _PluginType('launchers', Launcher.register_launcher)]


def _load_plugins(path: str, type: _PluginType) -> None:
    for mod in pkgutil.iter_modules(path=[path]):
        if not mod.ispkg and not mod.name[0] == '_':
            im = importlib.import_module('psij.{}.{}'.format(type.name, mod.name))
            var_name = '__PSI_J_{}__'.format(type.name.upper())
            if hasattr(im, var_name):
                classes = getattr(im, var_name)
                logger.debug('Found module "{}" with classes {}'.format(mod.name, classes))
                for cls in classes:
                    logger.debug('Registering {}'.format(cls))
                type.registration_method(cls)


def _find_plugins(path: str, type: _PluginType, ix: int) -> None:
    if ix == len(type.package):
        _load_plugins(path, type)
    else:
        for mod in pkgutil.iter_modules(path=[path]):
            if mod.ispkg and mod.name == type.package[ix]:
                _find_plugins(path + os.path.sep + mod.name, type, ix + 1)


seen = set()
for path in sys.path:
    path = os.path.realpath(path)
    if path in seen:
        logger.info('Ignoring duplicate entry in sys.path: {}'.format(path))
        continue
    seen.add(path)
    for type in TYPES:
        _find_plugins(path, type, 0)
