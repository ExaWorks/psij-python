from pathlib import Path
from typing import Optional, List, Dict, Any, Type
import sys

def path_object_to_full_path( obj ) -> str :
    p = None
    if obj :
        if type(obj).__name__ == "str" :
            p = obj
        elif type(obj).__name__ == "PosixPath" :
            p = obj.as_posix()
        else :
            print(type(obj))
            sys.exit("This type " + type(obj).__name__  + " for a path is not supported, use pathlib instead")
    return p