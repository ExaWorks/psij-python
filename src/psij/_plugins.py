import importlib
import logging
from bisect import bisect_left
from packaging.specifiers import SpecifierSet
from types import ModuleType
from typing import Tuple, Dict, List, Union, Type, Any, Optional, TypeVar

from psij.descriptor import Descriptor, _VersionEntry

logger = logging.getLogger(__name__)


def _getfile(o: Optional[Union[Type[Any], ModuleType]]) -> str:
    if o is None:
        return ''
    else:
        return o.__psij_file__  # type: ignore


def _split_cls_name(cls: str) -> Tuple[str, str]:
    comps = cls.split('.')
    return '.'.join(comps[:-1]), comps[-1]


T = TypeVar('T')


def _register_plugin(desc: Descriptor, root_path: str, type: str,
                     store: Dict[str, List[_VersionEntry[T]]]) -> None:
    """
    Registers a class with a certain base class through a :class:`~psij.Descriptor`.

    This is used internally to dynamically find and register :class:`~psij.JobExecutor` and
    :class:`~psij.Launcher` classes.

    Parameters
    ----------
    desc:
        a descriptor whose `cls` property must point to a class that has `cls` as a base class.
    type:
        the type of class being registered (either "executor" or "launcher")
    store:
        a dictionary where the registered plugins are being stored
    """
    module, cls_name = _split_cls_name(desc.cls)
    cls: Optional[Type[Any]] = None
    exc = None
    mod_path = root_path + '/' + module.replace('.', '/') + '.py'
    try:
        spec = importlib.util.spec_from_file_location(module, mod_path)
        if spec is None:
            raise Exception('Failed to load %s' % mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore
        cls = getattr(mod, cls_name)
        cls.__psij_file__ = mod_path  # type: ignore
    except Exception as ex:
        s = str(ex)
        logger.info(s)
        exc = ex

    entry: _VersionEntry[T] = _VersionEntry(desc=desc, plugin_path=mod_path, ecls=cls, exc=exc)

    _insert(store, desc.name, type, entry, desc, cls)
    if desc.aliases is not None:
        for alias in desc.aliases:
            _insert(store, alias, type, entry, desc, cls)


def _insert(store: Dict[str, List[_VersionEntry[T]]], name: str, type: str, entry: _VersionEntry[T],
            desc: Descriptor, cls: Optional[Type[T]]) -> None:
    name = desc.name.lower()
    if name not in store:
        store[name] = []
    existing = store[name]

    # check if an object with this version already exists
    index = bisect_left(existing, entry)
    if index != len(existing) and existing[index].version == desc.version:
        p1 = _getfile(existing[index].ecls)
        p2 = _getfile(cls)
        if p1 == p2:
            # can happen if PYTHONPATH has, e.g., a/, a/b/, so ignore silently
            return
        if type == 'executor':
            txt = 'An executor'
        else:
            txt = 'A launcher'
        raise ValueError(('%s by the name "%s" with version %s is already '
                          'registered. Existing path: %s; current path: %s' % (txt, name,
                                                                               desc.version,
                                                                               p1, p2)))
    existing.insert(index, entry)


def _print_plugin_status(store: Dict[str, List[_VersionEntry[T]]], type: str) -> None:
    for k, v in store.items():
        for ve in v:
            print('%s %s %s:\n'
                  '\tdescriptor: %s\n'
                  '\t    plugin: %s\n'
                  '\t     error: %s' % (type.capitalize(), k, ve.version, ve.desc_path,
                                        ve.plugin_path, ve.exc))


def _get_names(store: Dict[str, Any]) -> str:
    return ', '.join(filter(lambda x: x[0] != '_', store.keys()))


def _get_plugin_class(name: str, version_constraint: Optional[str], type: str,
                      store: Dict[str, List[_VersionEntry[T]]]) -> _VersionEntry[T]:
    name = name.lower()
    if name not in store:
        raise ValueError('No such {} "{}". Available {}s: {}'.format(type, name, type,
                                                                     _get_names(store)))
    versions = store[name]
    selected = None
    if version_constraint:
        pred = SpecifierSet(version_constraint)
        for entry in reversed(versions):
            if entry.version in pred:
                selected = entry
    else:
        selected = versions[-1]

    if selected is None:
        raise ValueError('No {} "{}" found to satisfy "{}"'.format(type, name, version_constraint))
    elif selected.exc is not None:
        raise ValueError('Unable to load {} {}'.format(type, name)) from selected.exc
    else:
        return selected
