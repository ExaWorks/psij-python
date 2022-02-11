from pathlib import Path
from typing import Optional, List, Dict, Any, Type
import sys

def path_object_to_full_path( obj : Optional[object] ) -> Optional[str] :
    p = None 
    if obj :
        if isinstance(obj, str):
            p = obj
        elif isinstance(obj, Path):
            p = obj.as_posix()
        else :
            print(type(obj))
            sys.exit("This type " + type(obj).__name__  + " for a path is not supported, use pathlib instead")
    return p