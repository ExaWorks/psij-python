"""This package contains all launcher implementations.

Launcher implementations must be in this package in order for them to be registered automatically.
Alternatively, you may register a launcher implementation using
:func:`psij.job_launcher.Launcher.register_launcher`.
"""

from .single import SingleLauncher
from .multiple import MultipleLauncher
from .mpirun import MPILauncher
from .srun import SrunLauncher
from .jsrun import JsrunLauncher
from .aprun import AprunLauncher

__all__ = [
    "SingleLauncher",
    "MultipleLauncher",
    "MPILauncher",
    "SrunLauncher",
    "JsrunLauncher",
    "AprunLauncher",
]
