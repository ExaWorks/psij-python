from abc import ABC, abstractmethod
from typing import Optional, Tuple

from psij.exceptions import InvalidJobException


class ResourceSpec(ABC):
    """
    A base class for resource specifications.

    The `ResourceSpec` class is an abstract base class for all possible resource specification
    classes in PSI/J.
    """

    @property
    @abstractmethod
    def version(self) -> int:
        """Returns the version of this resource specification class."""
        pass


class ResourceSpecV1(ResourceSpec):
    """This class implements V1 of the PSI/J resource specification."""

    def __init__(self, node_count: Optional[int] = None,
                 process_count: Optional[int] = None,
                 processes_per_node: Optional[int] = None,
                 cpu_cores_per_process: Optional[int] = None,
                 gpu_cores_per_process: Optional[int] = None,
                 exclusive_node_use: bool = True) -> None:
        """
        Constructs a `ResourceSpecV1` object and optionally initializes its properties.

        :param node_count: If specified, request that the backend allocate this many compute nodes
            for the job. This defaults to `1` if `exclusive_node_use` is `True`. This property
            cannot be specified concurrently with `process_count`.
        :param process_count: If specified, instruct the backend to start this many process
            instances. This defaults to `1`. This property cannot be specified concurrently with
            `node_count`.
        :param processes_per_node: Instruct the backend to run this many process instances on each
            node. In principle, `process_count = node_count * processes_per_node`. Defaults to `1`.
        :param cpu_cores_per_process: Request this many CPU cores for each process instance. This
            property is used by a backend to calculate the number of nodes from the `process_count`
        :param gpu_cores_per_process:
        :param exclusive_node_use:
        """
        self.node_count = node_count
        self.process_count = process_count
        self._check_constraints()
        self.processes_per_node = processes_per_node
        self.cpu_cores_per_process = cpu_cores_per_process
        self.gpu_cores_per_process = gpu_cores_per_process
        self.exclusive_node_use = exclusive_node_use

    def _check_constraints(self) -> None:
        if self.node_count is not None and self.process_count is not None:
            raise InvalidJobException('Cannot simmultaneously specify both node_count and '
                                      'process_count')

    def _compute_counts(self) -> Tuple[int, int, int]:
        if self.processes_per_node is None:
            ppn = 1
        else:
            ppn = self.processes_per_node
        if self.process_count is None:
            if self.node_count is None:
                return (1, 1, ppn)
            else:
                return (self.node_count, 1, ppn)
        else:
            if self.node_count is None:
                return (int(self.process_count / ppn), self.process_count, ppn)
            else:
                raise InvalidJobException('Cannot simmultaneously specify both node_count and '
                                          'process_count')

    @property
    def computed_node_count(self) -> int:
        """
        Returns or calculates a node count.

        If the :attr:`node_count` property is specified, this method returns it. If not, a node
        count is calculated from the :attr:`process_count` and :attr:`processes_per_node`.

        :return: An integer value with the specified or calculated node count.
        """
        self._check_constraints()
        if self.node_count is not None:
            return self.node_count
        (nc, pc, ppn) = self._compute_counts()
        return nc

    @property
    def computed_process_count(self) -> int:
        """
        Returns or calculates a process count.

        If the :attr:`process_count` property is specified, this method returns it, otherwise it
        returns 1.

        :return: An integer value with either the value of :attr:`process_count` or one if the
            former is not specified.
        """
        self._check_constraints()
        if self.process_count is not None:
            return self.computed_process_count
        (nc, pc, ppn) = self._compute_counts()
        return pc

    @property
    def version(self) -> int:
        """Returns the version of this `ResourceSpec`, which is 1 for this class."""
        return 1
