"""This package contains all launcher implementations.

Launcher implementations must be in this package in order for them to be registered automatically.
Alternatively, you may register a launcher implementation using
:func:`psij.launchers.launcher.Launcher.register_launcher`.
"""

from .launcher import Launcher
from .single import SingleLauncher
from .multiple import MultipleLauncher
from .mpirun import MPILauncher

__all__ = ['Launcher', 'SingleLauncher', 'MultipleLauncher', 'MPILauncher']
