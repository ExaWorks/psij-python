from abc import ABC, abstractmethod
from typing import Optional, List

from psij.exceptions import InvalidJobException


def _nulls(objs: List[object]) -> int:
    s = 0
    for e in objs:
        if e is None:
            s += 1
    return s


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

        Some of the properties of this class are constrained. Specifically,
        `process_count = node_count * processes_per_node`. Specifying all constrained properties
        in a way that does not satisfy the constraint will result in an error. Specifying some
        of the constrained properties will result in the remaining one being inferred based on
        the constraint. This inference is done by this class. However, executor implementations
        may chose to delegate this inference to an underlying implementation and ignore the
        values inferred by this class.

        :param node_count: If specified, request that the backend allocate this many compute nodes
            for the job.
        :param process_count: If specified, instruct the backend to start this many process
            instances. This defaults to `1`.
        :param processes_per_node: Instruct the backend to run this many process instances on each
            node.
        :param cpu_cores_per_process: Request this many CPU cores for each process instance. This
            property is used by a backend to calculate the number of nodes from the `process_count`
        :param gpu_cores_per_process:
        :param exclusive_node_use:
        """
        self.node_count = node_count
        self.process_count = process_count
        self.processes_per_node = processes_per_node
        self.cpu_cores_per_process = cpu_cores_per_process
        self.gpu_cores_per_process = gpu_cores_per_process
        self.exclusive_node_use = exclusive_node_use
        self._check_constraints()

    def _check_constraints(self) -> None:
        nulls = [self.process_count, self.node_count, self.processes_per_node].count(None)
        self._computed_process_count = self.process_count
        self._computed_node_count = self.node_count
        self._computed_ppn = self.processes_per_node
        if nulls == 3:
            # nothing specified
            self._computed_process_count = 1
            self._computed_node_count = 1
            self._commputed_ppn = 1
        elif nulls == 2:
            if self.process_count is not None:
                self._computed_node_count = 1
                self._computed_ppn = self.process_count
            elif self.node_count is not None:
                self._computed_process_count = self.node_count
                self._computed_ppn = 1
            else:
                self._computed_process_count = self.processes_per_node
                self._computed_node_count = 1
        elif nulls == 1:
            if self.process_count is None:
                assert self.node_count is not None
                assert self.processes_per_node is not None
                self._computed_process_count = int(self.node_count * self.processes_per_node)
            elif self.node_count is None:
                assert self.process_count is not None
                assert self.processes_per_node is not None
                if self.process_count % self.processes_per_node != 0:
                    raise InvalidJobException('The process_count (%s) must be an integral multiple'
                                              ' of processes_per_node (%s)' %
                                              (self.process_count, self.processes_per_node))
                self._computed_node_count = self.process_count // self.processes_per_node
            else:
                assert self.process_count is not None
                assert self.node_count is not None
                if self.process_count % self.node_count != 0:
                    raise InvalidJobException('The process_count (%s) must be an integral multiple'
                                              ' of node_count (%s)' %
                                              (self.process_count, self.node_count))
                self._computed_ppn = self.process_count // self.node_count
        else:
            # all specified
            assert self.process_count is not None
            assert self.node_count is not None
            assert self.processes_per_node is not None
            if self.process_count != self.node_count * self.processes_per_node:
                raise InvalidJobException('The resources must satisfy the constraint '
                                          'process_count (%s) = node_count (%s) * '
                                          'processes_per_node (%s).' %
                                          (self.process_count, self.node_count,
                                           self.processes_per_node))

    @property
    def computed_node_count(self) -> int:
        """
        Returns or calculates a node count.

        If the `node_count` property is specified, this method returns it. If not, a node
        count is calculated from `process_count` and `processes_per_node`.

        :return: An integer value with the specified or calculated node count.
        """
        assert self._computed_node_count is not None
        return self._computed_node_count

    @property
    def computed_process_count(self) -> int:
        """
        Returns or calculates a process count.

        If the `process_count` property is specified, this method returns it, otherwise it
        returns 1.

        :return: An integer value with either the value of `process_count` or one if the
            former is not specified.
        """
        assert self._computed_process_count is not None
        return self._computed_process_count

    @property
    def computed_processes_per_node(self) -> int:
        """
        Returns or calculates the number of processes per node.

        If the `processes_per_node` property is specified, this method returns it, otherwise
        calculates it based on `process_count` and `node_count` if possible, or defaults to 1.

        :return: An integer value with either the value of `processes_per_node` or one if the
            former cannot be determined.
        """
        assert self._computed_ppn is not None
        return self._computed_ppn

    @property
    def version(self) -> int:
        """Returns the version of this `ResourceSpec`, which is 1 for this class."""
        return 1
