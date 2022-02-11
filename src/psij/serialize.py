from pathlib import Path
from typing import Optional, List, Dict
import sys

class Export(object):
    """A class for exporting psij data types."""

    def __init__(self) : self.version = ''


    @property
    def name(self) -> Optional[str]:
        """Returns the name of the job."""
        if self._name is None:
            return self.executable
        else:
            return self._name


    def to_dict(self,obj) -> dict :
        
        new_dict = {}
        
        if  type(obj).__name__ in ["JobSpec"] :
            new_dict = obj.to_dict
        else:
            sys.exit("Can't create dict, type " + type(obj).__name__ + " not supported" )

        return new_dict
    

class Import() :
    pass