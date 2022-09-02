from pathlib import Path
from typing import Optional, Dict, Any
from psij.job_spec import JobSpec
from psij.job_attributes import JobAttributes
import json


# TODO: fix dosctrings
class Export(object):
    """A class for exporting psij data types."""

    def __init__(self) -> None:
        """Initializes an export object."""
        self.version = ''
        self.name = ''

    def envelope(self, type: Optional[str] = None) -> Dict[str, Any]:
        """TODO."""
        envelope: Dict[str, Any]

        envelope = {
            'version': 0.1,
            'type': type,
            'data': None
        }

        return envelope

    def to_dict(self, obj: object) -> Dict[str, Any]:
        """Returns a dictionary representation of an object."""
        new_dict = {}

        if not isinstance(obj, JobSpec):
            raise TypeError("Can't create dict, type " + type(obj).__name__ + " not supported")

        new_dict = obj.to_dict

        return new_dict

    def export(self, obj: object, dest: str) -> bool:
        """Serializes an object to a file."""
        source_type = type(obj).__name__
        d = self.to_dict(obj)

        envelope = self.envelope(type=source_type)
        envelope['data'] = d

        with open(dest, 'w', encoding='utf-8') as f:
            json.dump(envelope, f, ensure_ascii=False, indent=4)

        return True


class Import():
    """A class for importing psij data types."""

    def _dict2spec(self, d: Dict[str, Any]) -> object:
        """Read a JobSpec from a dicttionary."""
        # Initial spec object
        spec = JobSpec()

        # Map properties to keys
        spec._name = d['name'] if 'name' in d else d['_name']
        spec.executable = d['executable']
        spec.arguments = d['arguments']

        spec.directory = Path(d['directory']) if ('directory' in d) and d['directory'] else None
        spec.inherit_environment = d['inherit_environment']
        spec.environment = d['environment']
        spec.stdin_path = Path(d['stdin_path']) if (
            'stdin_path' in d) and d['stdin_path'] else None
        spec.stdout_path = Path(d['stdout_path']) if (
            'stdout_path' in d) and d['stdout_path'] else None
        spec.stderr_path = Path(d['stderr_path']) if (
            'stderr_path' in d) and d['stderr_path'] else None
        spec.resources = d['resources']

        # Handle attributes property
        if d['attributes']:
            ja = JobAttributes()

            attributes = d['attributes']
            ja.duration = attributes['duration']
            ja.queue_name = attributes['queue_name']
            ja.reservation_id = attributes['reservation_id']
            ja._custom_attributes = attributes['custom_attributes'] \
                if "custom_attributes" in attributes else None

            spec.attributes = ja

        return spec

    def from_dict(self, hash: Dict[str, Any], target_type: str) -> object:
        """Reads an object from a dict."""
        if target_type != "JobSpec":
            raise TypeError("Can't create object, type " + target_type + " not supported")
        return self._dict2spec(hash)

    def load(self, src: str) -> object:
        """Loads an object from a file."""
        envelope = None
        with open(src, 'r', encoding='utf-8') as f:
            envelope = json.load(f)

        obj = self.from_dict(envelope['data'], target_type=envelope['type'])

        return obj
