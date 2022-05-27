import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from psij.job_attributes import JobAttributes
from psij.resource_spec import ResourceSpec

from psij.utils import path_object_to_full_path as o2p


class JobSpec(object):
    """A class to hold information about the characteristics of a:class:`~psij.Job`."""

    def __init__(self, name: Optional[str] = None, executable: Optional[str] = None,
                 arguments: Optional[List[str]] = None, directory: Optional[Path] = None,
                 inherit_environment: bool = True, environment: Optional[Dict[str, str]] = None,
                 stdin_path: Optional[Path] = None, stdout_path: Optional[Path] = None,
                 stderr_path: Optional[Path] = None, resources: Optional[ResourceSpec] = None,
                 attributes: Optional[JobAttributes] = None, pre_launch: Optional[Path] = None,
                 post_launch: Optional[Path] = None, launcher: Optional[str] = None):
        """
        Constructs a `JobSpec` object while allowing its properties to be initialized.

        :param name: A name for the job. The name plays no functional role except that
            :class:`~psij.JobExecutor` implementations may attempt to use the name to label the
            job as presented by the underlying implementation.
        :param executable: An executable, such as "/bin/date".
        :param arguments: The argument list to be passed to the executable. Unlike with execve(),
            the first element of the list will correspond to `argv[1]` when accessed by the invoked
            executable.
        :param directory: The directory, on the compute side, in which the executable is to be run
        :param inherit_environment: If this flag is set to `False`, the job starts with an empty
            environment. The only environment variables that will be accessible to the job are the
            ones specified by this property. If this flag is set to `True`, which is the default,
            the job will also have access to variables inherited from the environment in which the
            job is run.
        :param environment: A mapping of environment variable names to their respective values.
        :param stdin_path: Path to a file whose contents will be sent to the job's standard input.
        :param stdout_path: A path to a file in which to place the standard output stream of the
            job.
        :param stderr_path: A path to a file in which to place the standard error stream of the job.
        :param resources: The resource requirements specify the details of how the job is to be run
            on a cluster, such as the number and type of compute nodes used, etc.
        :param attributes: Job attributes are details about the job, such as the walltime, that are
            descriptive of how the job behaves. Attributes are, in principle, non-essential in that
            the job could run even though no attributes are specified. In practice, specifying a
            walltime is often necessary to prevent LRMs from prematurely terminating a job.
        :param pre_launch: An optional path to a pre-launch script. The pre-launch script is
            sourced before the launcher is invoked. It, therefore, runs on the service node of the
            job rather than on all of the compute nodes allocated to the job.
        :param post_launch: An optional path to a post-launch script. The post-launch script is
            sourced after all the ranks of the job executable complete and is sourced on the same
            node as the pre-launch script.
        :param launcher: The name of a launcher to use, such as "mpirun", "srun", "single", etc.
            For a list of available launchers,:ref:`launchers`
        """
        self._name = name
        self.executable = executable
        self.arguments = arguments
        self.directory = directory
        self.inherit_environment = inherit_environment
        self.environment = environment
        self.stdin_path = stdin_path
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path
        self.resources = resources
        self.attributes = attributes if attributes is not None else JobAttributes()
        self.pre_launch = pre_launch
        self.post_launch = post_launch
        self.launcher = launcher

        # TODO: `resources` is of type `ResourceSpec`, not `ResourceSpecV1`.  An
        #       connector trying to access `job.spec.resources.process_count`
        #       will thus face an `unknown member` warning.

    @property
    def name(self) -> Optional[str]:
        """Returns the name of the job."""
        if self._name is None:
            return self.executable
        else:
            return self._name

    @property
    def _init_job_spec_dict(self) -> Dict[str, Any]:
        """Returns jobspec structure as dict."""
        # convention:
        #  - if expected value is a string then the dict is initialized with an empty string
        # - if the expected value is an object than the key is initialzied with None

        job_spec: Dict[str, Any]
        job_spec = {
            'name': '',
            'executable': '',
            'arguments': [],
            'directory': None,
            'inherit_environment': True,
            'environment': {},
            'stdin_path': None,
            'stdout_path': None,
            'stderr_path': None,
            'resources': None,
            'attributes': None,
            'launcher': None
        }

        return job_spec

    @property
    def to_dict(self) -> Dict[str, Any]:
        """Returns a dictionary representation of this object."""
        d = self._init_job_spec_dict

        # Map properties to keys
        d['name'] = self.name
        d['executable'] = self.executable
        d['arguments'] = self.arguments
        d['directory'] = o2p(self.directory)
        d['inherit_environment'] = self.inherit_environment
        d['environment'] = self.environment
        d['stdin_path'] = o2p(self.stdin_path)
        d['stdout_path'] = o2p(self.stdout_path)
        d['stderr_path'] = o2p(self.stderr_path)
        d['resources'] = self.resources

        # Handle attributes property
        if self.attributes:
            d['attributes'] = {
                'duration': '',
                'queue_name': '',
                'project_name': '',
                'reservation_id': '',
                'custom_attributes': {},
            }
            for k, v in self.attributes.__dict__.items():
                if k in ['duration', 'queue_name', 'project_name', 'reservation_id']:
                    if v:
                        d['attributes'][k] = str(v)
                    else:
                        d['attributes'][k] = v
                elif k == "_custom_attributes":
                    if v:
                        for ck, cv in v.items():
                            if not type(cv).__name__ in ['str',
                                                         'list',
                                                         'dict',
                                                         'NoneType',
                                                         'bool',
                                                         'int']:
                                sys.stderr.write("Unsupported type "
                                                 + type(cv).__name__
                                                 + " in JobAttributes.custom_attributes for key "
                                                 + ck
                                                 + ", skipping\n")
                        else:
                            if ck:
                                d['attributes']['custom_attributes'][ck] = str(cv)
                            else:
                                d['attributes']['custom_attributes'][ck] = cv
                else:
                    sys.stderr.write("Unsupported attribute " + k + ", skipping attribute\n")
        else:
            d['attributes'] = None

        if self.resources:

            d['resources'] = {
                'node_count': None,
                'process_count': None,
                'process_per_node': None,
                'cpu_cores_per_process': None,
                'gpu_cores_per_process': None,
                'exclusive_node_use': None
            }
            r = self.resources.__dict__
            for k in d['resources'].keys():
                d['resources'][k] = r[k] if k in r else None

        return d
