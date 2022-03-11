from pathlib import Path
from typing import Optional
import sys


# TODO: this should not be in a separate file if it is only used in one place
def path_object_to_full_path(obj: Optional[object]) -> Optional[str]:
    """Converts this path to a string?."""
    p = None
    if obj:
        if isinstance(obj, str):
            p = obj
        elif isinstance(obj, Path):
            p = obj.as_posix()
        else:
            print(type(obj))
            # TODO: library methods should not exit and bring everything down on errors
            # TODO: instead, they should throw exceptions
            sys.exit("This type " + type(obj).__name__
                     + " for a path is not supported, use pathlib instead")
    return p
