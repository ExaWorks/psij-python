import inspect
import json
import typing
from abc import ABC, abstractmethod
from datetime import timedelta
from io import StringIO, TextIOBase
from pathlib import Path
from typing import Optional, Dict, Union, List, IO, AnyStr, TextIO

from psij import ResourceSpec
from psij.job_attributes import JobAttributes
from psij.job_spec import JobSpec


NoneType = type(None)


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

    def dump(self, spec: JobSpec, stream: IO[AnyStr]) -> None:
        """
        Serialize the given :class:`~psij.JobSpec` and write the results to `stream`.

        Parameters
        ----------
        spec
            The :class:`~psij.JobSpec` to serialize.
        stream
            A stream to write the serialized `JobSpec` to. Concrete serializers may require that
            the stream be a binary or text stream.
        """
        # all `_from_*` methods relate to serialization
        self._dump_dict(self._from_spec(spec), stream)

    def load(self, stream: IO[AnyStr]) -> JobSpec:
        """
        Deserialize the contents of a stream to an instance of :class:`~psij.JobSpec`.

        Parameters
        ----------
        stream
            A stream to read the serialized `JobSpec` from. Concrete serializers may require that
            the stream be a binary or text stream.
        Returns
        -------
        The deserialized `JobSpec` instance.
        """
        # all `_tp_*` methods relate to deserialization
        return self._to_spec(self._load_dict(stream))

    def dumps(self, spec: JobSpec) -> str:
        """
        Serialize the given :class:`~psij.JobSpec` to a string.

        Serializer implementations that use a binary protocol must override this method and raise
        an error.

        Parameters
        ----------
        spec
            The :class:`~psij.JobSpec` to serialize.
        Returns
        -------
        A string representation of the `spec`.
        """
        f = StringIO()
        self.dump(spec, f)
        return f.getvalue()

    def loads(self, s: str) -> JobSpec:
        """
        Deserialize a :class:`~psij.JobSpec` from a string.

        Serializer implementations that use a binary protocol must override this method and raise
        an error.

        Parameters
        ----------
        s
            The string containing the serialized representation of a `JobSpec`.
        Returns
        -------
        The deserialized `JobSpec` instance.
        """
        f = StringIO(s)
        return self.load(f)

    @abstractmethod
    def _dump_dict(self, dict: Dict[str, object], stream: IO[AnyStr]) -> None:
        pass

    @abstractmethod
    def _load_dict(self, stream: IO[AnyStr]) -> Dict[str, object]:
        pass

    def _from_spec(self, o: JobSpec) -> Dict[str, object]:
        return self._from_psij_object(o)

    def _from_psij_object(self, o: Union[JobSpec, JobAttributes, ResourceSpec]) \
            -> Dict[str, object]:
        r = {}

        sig = inspect.signature(o.__class__.__init__)
        types = typing.get_type_hints(o.__class__.__init__)

        for name, param in sig.parameters.items():
            if name == 'self':
                continue
            t = self._canonicalize_type(types[name])
            value = getattr(o, name)
            if value != param.default:
                # only explicitly serialize if it's not the default
                r[name] = self._from_object(value, t)

        # special handling for things with versions, such as ResourceSpec
        if hasattr(o, 'version'):
            r['__version'] = getattr(o, 'version')

        return r

    def _canonicalize_type(self, t: object) -> object:
        # generics don't appear to be subclasses of Type, so we can't really use Type for t
        origin = typing.get_origin(t)
        if origin == Optional:
            # Python converts Optional[T] to Union[T, None], so this shouldn't happen
            return typing.get_args(t)[0]
        elif origin == Union:
            args = typing.get_args(t)
            if args[0] == NoneType:
                return args[1]
            elif args[1] == NoneType:
                return args[0]
            else:
                return t
        else:
            return t

    def _from_object(self, o: object, t: object) -> object:
        if isinstance(t, type) and inspect.isclass(t):
            if issubclass(t, JobAttributes):
                assert isinstance(o, JobAttributes)
                return self._from_psij_object(o)
            if issubclass(t, ResourceSpec):
                assert isinstance(o, ResourceSpec)
                return self._from_psij_object(o)
            if str == t or Path == t:
                return str(o)
            if bool == t:
                return bool(o)
            if int == t:
                assert isinstance(o, int)
                return o
            if issubclass(t, timedelta):
                assert isinstance(o, timedelta)
                return self._from_timedelta(o)
        else:
            if t == Union[str, Path] or t == Optional[Union[str, Path]]:
                return str(o)
            if typing.get_origin(t) == dict:
                assert isinstance(o, dict)
                return self._from_dict(o)
            if typing.get_origin(t) == list:
                assert isinstance(o, list)
                return self._from_list(o)
        raise ValueError('Cannot convert type "%s".' % t)

    def _from_dict(self, d: Dict[object, object]) -> Dict[str, object]:
        r = {}
        for k, v in d.items():
            if not isinstance(k, str):
                raise ValueError('Cannot convert dictionary with non-string keys. '
                                 'Offending key was "%s"' % k)
            # we don't have an expected type here, so use the type of the object
            r[k] = self._from_object(v, type(v))
        return r

    def _from_list(self, lst: List[object]) -> List[object]:
        return [self._from_object(v, type(v)) for v in lst]

    def _from_timedelta(self, t: timedelta) -> str:
        return "%s s" % t.total_seconds()

    def _to_spec(self, d: Dict[str, object]) -> JobSpec:
        r = self._to_psij_object(d, JobSpec)
        assert isinstance(r, JobSpec)
        return r

    def _to_psij_object(self, d: Dict[str, object], expected_type: type) -> object:
        processed_keys = set()

        if '__version' in d:
            assert hasattr(expected_type, 'get_instance')
            r = getattr(expected_type, 'get_instance')(d['__version'])
            expected_type = r.__class__
            processed_keys.add('__version')
        else:
            r = expected_type()

        sig = inspect.signature(getattr(expected_type, '__init__'))
        types = typing.get_type_hints(getattr(expected_type, '__init__'))

        for name, param in sig.parameters.items():
            if name == 'self' or name.startswith('__') or name not in d:
                continue
            t = self._canonicalize_type(types[name])
            value = d[name]
            if value != param.default:
                print(name)
                setattr(r, name, self._to_object(value, t))
            processed_keys.add(name)

        for name in d.keys():
            if name not in processed_keys:
                raise ValueError('Unexpected key "%s"' % name)

        return r

    def _to_object(self, s: object, t: object) -> object:
        if isinstance(t, type) and inspect.isclass(t):
            if issubclass(t, JobAttributes) or issubclass(t, ResourceSpec):
                assert isinstance(s, dict)
                return self._to_psij_object(s, t)
            if str == t or Path == t:
                return str(s)
            if bool == t:
                return bool(s)
            if int == t:
                assert isinstance(s, int)
                return s
            if issubclass(t, timedelta):
                assert isinstance(s, str)
                return JobAttributes.parse_walltime(s)
        else:
            if t == Union[str, Path] or t == Optional[Union[str, Path]]:
                assert isinstance(s, str)
                return Path(s)
            if typing.get_origin(t) == dict:
                assert isinstance(s, dict)
                return self._to_dict(s)
            if typing.get_origin(t) == list:
                assert isinstance(s, list)
                return self._to_list(s)
        raise ValueError('Cannot convert type "%s".' % t)

    def _to_dict(self, d: Dict[str, object]) -> Dict[str, object]:
        r = {}

        for k, v in d.items():
            if not isinstance(k, str):
                raise ValueError('Cannot convert dictionary with non-string keys. '
                                 'Offending key was "%s"' % k)
            # we don't have an expected type here, so use the type of the object
            r[k] = self._to_object(v, type(v))

        return r

    def _to_list(self, lst: List[object]) -> List[object]:
        return [self._to_object(v, type(v)) for v in lst]


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
