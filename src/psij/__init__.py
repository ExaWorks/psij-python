"""The package containing the jobs module of this PSI implementation."""
import importlib
import logging
import os
import pkgutil
import sys
from typing import Callable, TypeVar

from psij.descriptor import Descriptor
from .exceptions import SubmitException, InvalidJobException
from .job import Job, JobStatusCallback
from .job_attributes import JobAttributes
from .job_executor import JobExecutor
from .job_executor_config import JobExecutorConfig
from .job_launcher import Launcher
from .job_spec import JobSpec
from .job_state import JobState
from .job_status import JobStatus
from .resource_spec import ResourceSpec, ResourceSpecV1
from .version import VERSION

__version__ = VERSION

__all__ = [
    'JobExecutor', 'JobExecutorConfig', 'Job', 'JobStatusCallback', 'JobSpec', 'JobAttributes',
    'JobStatus', 'JobState', 'ResourceSpec', 'ResourceSpecV1', 'Launcher', 'SubmitException',
    'InvalidJobException', 'UnreachableStateException'
]

logger = logging.getLogger(__name__)

T = TypeVar('T')


class _PluginType:
    def __init__(self, name: str, registration_method: Callable[[Descriptor, str], None]):
        self.name = name
        self.registration_method = registration_method


PACKAGE = ['psij-descriptors']


TYPES = [_PluginType('executors', JobExecutor.register_executor),
         _PluginType('launchers', Launcher.register_launcher)]


def _load_plugins(root: str, full_path: str, mod: pkgutil.ModuleInfo) -> None:
    if mod.ispkg:
        return
    logger.debug('Attempting to load %s from %s', mod.name, path)
    spec = mod.module_finder.find_spec(mod.name, None)
    try:
        if spec is None:
            raise Exception('Could not find module "%s"' % mod.name)
        im = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(im)  # type: ignore
        full_mod_path = spec.origin

        for _type in TYPES:
            var_name = '__PSI_J_{}__'.format(_type.name.upper())
            if hasattr(im, var_name):
                classes = getattr(im, var_name)
                logger.debug('Found module "{}" with classes {}'.format(mod.name, classes))
                for cls in classes:
                    if isinstance(cls, type) and issubclass(cls, JobExecutor):
                        logger.warning('Not loading old style executor in %s' %
                                       full_mod_path)
                    elif isinstance(cls, type) and issubclass(cls, Launcher):
                        logger.warning('Not loading old style launcher in %s' %
                                       full_mod_path)
                    elif isinstance(cls, Descriptor):
                        logger.debug('Registering {}'.format(cls))
                        cls.path = full_mod_path
                        _type.registration_method(cls, root)
                    else:
                        logger.warning('Cannot load plugin. Expected an instance of '
                                       'Descriptor in %s' % full_mod_path)
    except Exception as ex:
        logger.warning('Could not import %s: %s' % (full_mod_path, ex))
        logger.debug(ex, exc_info=True)


def _find_plugins(root: str, path: str) -> None:
    full_path = '/'.join([path] + PACKAGE)
    for mod in pkgutil.iter_modules(path=[full_path]):
        _load_plugins(root, full_path, mod)


seen_paths = set()


for path in sys.path:
    path = os.path.realpath(path)
    if path in seen_paths:
        logger.info('Ignoring duplicate entry in sys.path: {}'.format(path))
        continue
    seen_paths.add(path)
    _find_plugins(path, path)
