from distutils.version import StrictVersion, Version
from typing import TypeVar, Generic, Optional, Type

T = TypeVar('T')


class _VersionEntry(Generic[T]):
    def __init__(self, version: Version,
                 desc_path: Optional[str] = None,
                 plugin_path: Optional[str] = None,
                 ecls: Optional[Type[T]] = None,
                 exc: Optional[Exception] = None) -> None:
        self.version = version
        self.desc_path = desc_path
        self.plugin_path = plugin_path
        self.ecls = ecls
        self.exc = exc

    def __cmp__(self, other: '_VersionEntry[T]') -> int:
        if self.version == other.version:
            return 0
        elif self.version < other.version:
            return -1
        else:
            return 1

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _VersionEntry):
            return False
        return self.version == other.version

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, _VersionEntry):
            return NotImplemented
        return self.version < other.version

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, _VersionEntry):
            return NotImplemented
        return self.version > other.version


class Descriptor(object):
    """
    This class is used to enable PSI/J to discover and register executors and/or launchers.

    Executors wanting to register with PSI/J must place an instance of this class in a global
    module list named `__PSI_J_EXECUTORS__` or `__PSI_J_LAUNCHERS__` in a module placed in the
    `psij-descriptors` package. In other words, in order to automatically register an executor or
    launcher, a python file should be created inside a `psij-descriptors` package, such as:

    .. code-block:: none

        <project_root>/
            src/
                psij-descriptors/
                    descriptors_for_project.py

    The contents of `descriptors_for_project.py` could then be as follows:

    .. code-block:: python

        from distutils.version import StrictVersion
        from psij.descriptor import Descriptor

        __PSI_J_EXECUTORS__ = [
            Descriptor(name=<name>, version=StrictVersion(<version_str>),
                       cls=<fqn_str>),
            ...
        ]

        __PSI_J_LAUNCHERS__ = [
            Descriptor(name=<name>, version=StrictVersion(<version_str>),
                       cls=<fqn_str>),
            ...
        ]

    where `<name>` stands for the name used to instantiate the executor or launcher,
    `<version_str>` is a version string such as `1.0.2`, and `<fqn_str>` is the fully qualified
    class name that implements the executor or launcher such as
    `psij.executors.local.LocalJobExecutor`.
    """

    def __init__(self, name: str, version: StrictVersion, cls: str) -> None:
        """
        Initializes a descriptor.

        Parameters
        ----------
        name
            The name of the executor or launcher. The automatic registration system will register
            the executor or launcher using this name. That is, the executor or launcher represented
            by this descriptor will be available for instantiation using either
            :meth:`~psij.job_executor.JobExecutor.get_instance` or
            :meth:`~psij.job_launcher.Launcher.get_instance`
        version:
            The version of the executor/launcher. Multiple versions can be registered under a
            single name.
        cls:
            A fully qualified name pointing to the class implementing an executor or launcher.
        """
        self.name = name
        self.version = version
        self.cls = cls
        self.path: Optional[str] = None

    def __repr__(self) -> str:
        """Returns a string representation of this descriptor."""
        return 'Descriptor(name=%s, path=%s)' % (self.name, self.path)
