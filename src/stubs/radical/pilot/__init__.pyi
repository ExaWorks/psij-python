from .states import *
from .constants import *
from .agent import Agent_0 as Agent_0, Agent_n as Agent_n
from .context import Context as Context
from .deprecated import ComputePilot as ComputePilot, ComputePilotDescription as ComputePilotDescription, ComputeUnit as ComputeUnit, ComputeUnitDescription as ComputeUnitDescription, UnitManager as UnitManager
from .pilot import Pilot as Pilot
from .pilot_description import PilotDescription as PilotDescription
from .pilot_manager import PilotManager as PilotManager
from .raptor import Master as Master, Worker as Worker
from .session import Session as Session
from .task import Task as Task
from .task_description import CUDA as CUDA, FUNC as FUNC, MPI as MPI, OpenMP as OpenMP, POSIX as POSIX
from .task_manager import TaskManager as TaskManager
from typing import Any, Dict

version_short: Any
version_detail: Any
version_base: Any
version_branch: Any
sdist_name: Any
sdist_path: Any
version = version_short

def TaskDescription(from_dict: Dict[str, Any]) -> Dict[str, Any]: ...
