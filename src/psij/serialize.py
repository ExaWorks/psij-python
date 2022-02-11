from pathlib import Path
from typing import Optional, List, Dict
from psij.job_spec import JobSpec
from psij.job_attributes import JobAttributes
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
    
    
    def _dict2spec(self,d)  :
        
        # Initial spec object
        spec = JobSpec()
        
        # Map properties to keys
        spec._name = d['name'] if 'name' in d else d['_name'] 
        spec.executable =  d['executable']   
        spec.arguments = d['arguments']
        
        spec.directory = Path(d['directory']) if ('directory' in d) and d['directory'] else None
        spec.inherit_environment = d['inherit_environment']
        spec.environment = d['environment'] 
        spec.stdin_path = Path(d['stdin_path']) if ('stdin_path' in d) and d['stdin_path'] else None
        spec.stdout_path = Path(d['stdout_path']) if ('stdout_path' in d) and d['stdout_path'] else None
        spec.stderr_path = Path(d['stderr_path']) if ('stderr_path' in d) and d['stderr_path'] else None
        spec.resources = d['resources'] 
        
        # Handle attributes property
        if d['attributes'] :
            ja = JobAttributes()
            
            attributes = d['attributes'] 
            ja.duration = attributes['duration']
            ja.queue_name = attributes['queue_name']
            ja.reservation_id = attributes['reservation_id']
            ja.custom_attributes = attributes['custom_attributes']
            
            spec.attributes = ja
        print(spec)
        return spec
    
    def from_dict(self,hash, target_type=None) :
        
        if  target_type == "JobSpec" :
            return(self._dict2spec(hash))
        else:
            sys.exit("Can't create dict,  type " + target_type  + " not supported" )

     
        
        