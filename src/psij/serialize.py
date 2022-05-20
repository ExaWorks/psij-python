from pathlib import Path
from typing import Optional, Dict, Any
from psij.job_spec import JobSpec
from psij.job_attributes import JobAttributes
import sys
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

        if isinstance(obj, JobSpec):
            new_dict = obj.to_dict
        else:
            sys.exit("Can't create dict, type " + type(obj).__name__ + " not supported")

        return new_dict

    def export(self, obj: Optional[object] = None, dest: Optional[str] = None) -> bool:
        """Serializes an object to a file."""
        if not dest:
            sys.exit("Cannot export, missing destinstion file")
        if not obj:
            sys.exit("Cannot export, missing object")

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

    def from_dict(self, hash: Dict[str, Any], target_type: Optional[str] = None) -> object:
        """Reads an object from a dict."""
        if target_type == "JobSpec":
            return(self._dict2spec(hash))
        else:
            sys.exit("Can't create dict,  type " + str(target_type) + " not supported")

    def load(self, src: Optional[str] = None) -> object:
        """Loads an object from a file."""
        if not src:
            sys.exit("Cannot import, missing source file")

        envelope = None
        with open(src, 'r', encoding='utf-8') as f:
            envelope = json.load(f)

        obj = self.from_dict(envelope['data'], target_type=envelope['type'])

        return obj
