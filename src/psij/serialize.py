import collections.abc
import inspect
import json
import logging
import typing
from abc import ABC, abstractmethod
from datetime import timedelta
from enum import Enum
from io import StringIO, TextIOBase
from pathlib import Path, PosixPath, PurePath
from typing import Optional, Dict, Union, List, IO, AnyStr, TextIO, Tuple

from psij import ResourceSpec, ResourceSpecV1
from psij.job_attributes import JobAttributes
from psij.job_spec import JobSpec
from psij.job_status import JobStatus
from psij.job_state import JobState
from psij.staging import StageOut, StageIn, URI

logger = logging.getLogger(__name__)


NoneType = type(None)


PSIJSerializable = Union[JobSpec, JobStatus]


def _canonicalize_type(t: type) -> type:
    # generics don't appear to be subclasses of Type, so we can't really use Type for t
    origin = typing.get_origin(t)
    if origin == Optional:
        # Python converts Optional[T] to Union[T, None], so this shouldn't happen
        r = typing.get_args(t)[0]
    elif origin == Union:
        args = typing.get_args(t)
        if args[0] == NoneType:
            r = args[1]
        elif args[1] == NoneType:
            r = args[0]
        else:
            r = t
    else:
        r = t
    # assert isinstance(r, type)  # List[T] is in fact not an instance of type
    return r  # type: ignore


def _get_typing_info(t: type) -> Dict[str, Tuple[type, object]]:
    sig = inspect.signature(getattr(t, '__init__'))
    types = typing.get_type_hints(getattr(t, '__init__'))
    r = {}

    for name, param in sig.parameters.items():
        if name == 'self' or name.startswith('__'):
            continue
        t = _canonicalize_type(types[name])
        r[name] = (t, param.default)
    return r


def _init_typing_info() -> Dict[type, Dict[str, Tuple[type, object]]]:
    sigs = {}
    for t in [JobSpec, ResourceSpecV1, JobAttributes, JobStatus, StageIn, StageOut]:
        sigs[t] = _get_typing_info(t)
    return sigs


_SIGNATURES = _init_typing_info()


def _signature(t: type) -> Dict[str, Tuple[type, object]]:
    try:
        return _SIGNATURES[t]
    except KeyError:
        import traceback
        traceback.print_stack()
        logger.warning('Missing cached signature for %s', t)
        r = _get_typing_info(t)
        _SIGNATURES[t] = r
        return r


class Serializer(ABC):
    """
    A base class for serializers.

    This class takes care of converting a :class:`~psij.JobSpec` instance, including all its
    properties, into an intermediate representation consisting of a tree of standard dictionaries
    and lists, where dictionary keys are guaranteed to be strings and values are limited to
    dictionaries, lists, `str`, `int`, and `bool`. It also takes care of making the reverse
    conversion. Concrete implementations of serializers should extend this class and implement the
    `_dump_dict` and `_load_dict` methods, which convert the intermediate representation to the
    actual serialized format.

    Serializer implementations can also directly override the `dump`, `dumps`, `load`, and `loads`
    methods to bypass the intermediate representations and implement (de)serialization directly.
    """

    def dump(self, obj: PSIJSerializable, stream: IO[AnyStr]) -> None:
        """
        Serialize the given :class:`~psij.serialize.PSIJSerializable`.

        Parameters
        ----------
        obj
            The :class:`~psij.serialize.PSIJSerializable` object to serialize.
        stream
            A stream to write the serialized object to. Concrete serializers may require that
            the stream be a binary or text stream.
        """
        # all `_from_*` methods relate to serialization
        self._dump_dict(self._from_psij_object(obj), stream)

    def load(self, stream: IO[AnyStr]) -> PSIJSerializable:
        """
        Deserialize the contents of a stream to an instance of
        :class:`~psij.serialize.PSIJSerializable`

        Parameters
        ----------
        stream
            A stream to read the serialized `JobSpec` from. Concrete serializers may require that
            the stream be a binary or text stream.
        Returns
        -------
        The deserialized object.
        """
        # all `_tp_*` methods relate to deserialization
        return self._to_psij_object(self._load_dict(stream))

    def dumps(self, obj: PSIJSerializable) -> str:
        """
        Serialize the given :class:`~psij.serialize.PSIJSerializable` to a string.

        Serializer implementations that use a binary protocol must override this method and raise
        an error.

        Parameters
        ----------
        obj
            The :class:`~psij.serialize.PSIJSerializable` to serialize.
        Returns
        -------
        A string representation of the object.
        """
        f = StringIO()
        self.dump(obj, f)
        return f.getvalue()

    def dumpd(self, obj: PSIJSerializable) -> Dict[str, object]:
        """
        Converts the given object to a dictionary representation.

        Parameters
        ----------
        obj
            The object to convert.

        Returns
        -------
            A dictionary representing the object.
        """
        return self._from_psij_object(obj)

    def loads(self, s: str) -> PSIJSerializable:
        """
        Deserialize a :class:`~psij.serialize.PSIJSerializable` from a string.

        Serializer implementations that use a binary protocol must override this method and raise
        an error.

        Parameters
        ----------
        s
            The string containing the serialized representation of the object.
        Returns
        -------
        The deserialized object.
        """
        f = StringIO(s)
        return self.load(f)

    def loadd(self, d: Dict[str, object]) -> PSIJSerializable:
        """
        Converts a dictionary/list representation of an object to an instance.

        Parameters
        ----------
        d
            A dictionary obtained using :meth:`~psij.serialize.Serializer.dumpd`.

        Returns
        -------
            An instance of a :class:`~psij.serialize.PSIJSerializable` represented
            by `d`.
        """
        return self._to_psij_object(d)

    @abstractmethod
    def _dump_dict(self, dict: Dict[str, object], stream: IO[AnyStr]) -> None:
        pass

    @abstractmethod
    def _load_dict(self, stream: IO[AnyStr]) -> Dict[str, object]:
        pass

    def _from_psij_object(self, o: Union[JobSpec, JobAttributes, ResourceSpec, JobStatus,
                          JobState]) -> Dict[str, object]:
        r = {}

        sig = _signature(o.__class__)

        for name, (t, default) in sig.items():
            value = getattr(o, name)
            if value != default:
                # only explicitly serialize if it's not the default
                r[name] = self._from_object(value, t)

        # special handling for things with versions, such as ResourceSpec
        if hasattr(o, 'version'):
            r['__version'] = getattr(o, 'version')

        return r

    def _from_object(self, o: object, t: object) -> object:
        if isinstance(t, type) and inspect.isclass(t):
            for cls in [JobAttributes, ResourceSpec, JobStatus, StageIn, StageOut]:
                if issubclass(t, cls):
                    assert isinstance(o, cls)
                    return self._from_psij_object(o)  # type: ignore
            if issubclass(t, Enum):
                assert isinstance(o, Enum)
                return o.value
            if str == t or issubclass(t, PurePath):
                return str(o)
            if bool == t:
                return bool(o)
            if int == t:
                assert isinstance(o, int)
                return o
            if float == t:
                assert isinstance(o, float)
                return o
            if issubclass(t, timedelta):
                assert isinstance(o, timedelta)
                return self._from_timedelta(o)
        else:
            if t == Union[str, Path] or t == Optional[Union[str, Path]]:
                return str(o)
            if t == Union[URI, Path, str] or t == Optional[Union[URI, Path, str]]:
                return str(o)
            origin = typing.get_origin(t)
            if origin == dict:
                assert isinstance(o, dict)
                return self._from_dict(o)
            if origin == list or origin == collections.abc.Iterable:
                assert isinstance(o, typing.Iterable)
                return self._from_iterable(o)
            if origin == set:
                assert isinstance(o, set)
                return self._from_iterable(o)
        raise ValueError('Cannot serialize type "%s".' % t)

    def _from_dict(self, d: Dict[object, object]) -> Dict[str, object]:
        r = {}
        for k, v in d.items():
            if not isinstance(k, str):
                raise ValueError('Cannot convert dictionary with non-string keys. '
                                 'Offending key was "%s"' % k)
            # we don't have an expected type here, so use the type of the object
            r[k] = self._from_object(v, type(v))
        return r

    def _from_iterable(self, l: typing.Iterable[object]) -> List[object]:
        return [self._from_object(v, type(v)) for v in l]

    def _from_timedelta(self, t: timedelta) -> str:
        return "%s s" % t.total_seconds()

    def _to_spec(self, d: Dict[str, object]) -> JobSpec:
        r = self._to_psij_object(d, JobSpec)
        assert isinstance(r, JobSpec)
        return r

    def _guess_type(self, d: Dict[str, object]) -> type:
        if 'state' in d:
            return JobStatus
        else:
            return JobSpec

    def _to_psij_object(self, d: Dict[str, object],
                        expected_type: Optional[type] = None) -> PSIJSerializable:
        if expected_type is None:
            expected_type = self._guess_type(d)

        if '__version' in d:
            assert hasattr(expected_type, 'get_instance')
            r = getattr(expected_type, 'get_instance')(d['__version'])
            del d['__version']
            expected_type = r.__class__
            sig = _signature(expected_type)
            for name, value in d.items():
                try:
                    t, default = sig[name]
                except KeyError:
                    raise ValueError('Unexpected key "%s"' % name)
                if value != default:
                    setattr(r, name, self._to_object(value, t))
        else:
            sig = _signature(expected_type)
            kwargs = {}
            for name, value in d.items():
                try:
                    t, default = sig[name]
                except KeyError:
                    raise ValueError('Unexpected key "%s"' % name)
                if value != default:
                    kwargs[name] = self._to_object(value, t)
            r = expected_type(**kwargs)

        return r  # type: ignore

    def _to_object(self, s: object, t: object) -> object:
        if isinstance(t, type):
            if issubclass(t, StageIn):
                assert isinstance(s, dict)
                return self._to_psij_object(s, t)
            if issubclass(t, StageOut):
                assert isinstance(s, dict)
                return self._to_psij_object(s, t)
            if issubclass(t, JobAttributes) or issubclass(t, ResourceSpec):
                assert isinstance(s, dict)
                return self._to_psij_object(s, t)
            if issubclass(t, JobState):
                assert isinstance(s, int)
                return JobState(s)
            if str == t or Path == t:
                return str(s)
            if bool == t:
                return bool(s)
            if int == t:
                assert isinstance(s, int)
                return s
            if float == t:
                assert isinstance(s, float)
                return s
            if issubclass(t, timedelta):
                assert isinstance(s, str)
                return JobAttributes.parse_walltime(s)
        else:
            if t == Union[str, Path] or t == Optional[Union[str, Path]]:
                assert isinstance(s, str)
                return Path(s)
            if t == Union[URI, Path, str] or t == Optional[Union[URI, Path, str]]:
                assert isinstance(s, str)
                return URI(s)
            origin = typing.get_origin(t)
            print(f'Origin: {origin}[{typing.get_args(t)}]')
            if origin == dict:
                assert isinstance(s, dict)
                return self._to_dict(s)
            if origin == list or origin == collections.abc.Iterable:
                assert isinstance(s, list)
                arg = typing.get_args(t)[0]
                return self._to_list(s, arg)
            if origin == set:
                assert isinstance(s, set)
                return self._to_set(s)
        raise ValueError('Cannot deserialize type "%s, value: %s".' % (t, s))

    def _to_dict(self, d: Dict[str, object]) -> Dict[str, object]:
        r = {}

        for k, v in d.items():
            if not isinstance(k, str):
                raise ValueError('Cannot convert dictionary with non-string keys. '
                                 'Offending key was "%s"' % k)
            # we don't have an expected type here, so use the type of the object
            r[k] = self._to_object(v, type(v))

        return r

    def _to_list(self, lst: List[object], expected_type: Optional[type] = None) -> List[object]:
        if expected_type is None:
            return [self._to_object(v, type(v)) for v in lst]
        else:
            return [self._to_object(v, expected_type) for v in lst]

    def _to_set(self, lst: typing.Iterable[object]) -> typing.Set[object]:
        return {self._to_object(v, type(v)) for v in lst}


class JSONSerializer(Serializer):
    """A JSON serializer."""

    def _dump_dict(self, d: Dict[str, object], stream: IO[AnyStr]) -> None:
        assert isinstance(stream, TextIO) or isinstance(stream, TextIOBase), \
            'The JSON serializer requires a text stream.'

        json.dump(d, stream)

    def _load_dict(self, stream: IO[AnyStr]) -> Dict[str, object]:
        assert isinstance(stream, TextIO) or isinstance(stream, TextIOBase), \
            'The JSON serializer requires a text stream.'

        r = json.load(stream)
        assert isinstance(r, dict)
        return r
