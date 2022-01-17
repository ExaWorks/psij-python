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
        assert isinstance(other, _VersionEntry)
        return self.version < other.version

    def __gt__(self, other: object) -> bool:
        assert isinstance(other, _VersionEntry)
        return self.version > other.version


class _Descriptor(object):
    def __init__(self, name: str, version: StrictVersion, cls: str, path: Optional[str] = None):
        self.name = name
        self.version = version
        self.cls = cls
        self.path = path

    def __repr__(self) -> str:
        return '_Descriptor(name=%s, path=%s)' % (self.name, self.path)
