from datetime import timedelta, datetime
from pathlib import Path
from typing import Optional, Collection, List, Dict, IO, Union
import re

from psij import Job, JobStatus, JobState, SubmitException, JobSpec, ResourceSpecV1
from psij.executors.batch.batch_scheduler_executor import BatchSchedulerExecutor, \
    BatchSchedulerExecutorConfig, check_status_exit_code
from psij.executors.batch.script_generator import TemplatedScriptGenerator


_SQUEUE_COMMAND = 'squeue'


class SlurmExecutorConfig(BatchSchedulerExecutorConfig):
    """A configuration class for the Slurm executor."""

    pass


class SlurmJobExecutor(BatchSchedulerExecutor):
    """A :class:`~psij.JobExecutor` for the Slurm Workload Manager.

    The `Slurm Workload Manager <https://slurm.schedmd.com/overview.html>`_ is a
    widely used resource manager running on machines such as
    NERSC's Perlmutter, as well as a variety of LLNL machines.

    Uses the 'sbatch', 'squeue', and 'scancel' commands, respectively, to submit,
    monitor, and cancel jobs.

    Creates a batch script with #SBATCH directives when submitting a job.

    Renders all custom attributes set on a job's attributes with a `slurm.` prefix into
    corresponding Slurm directives with long-form parameters. For example,
    `job.spec.attributes.custom_attributes['slurm.qos'] = 'debug'` causes a directive
    `#SBATCH --qos=debug` to be placed in the submit script.
    """

    # see https://slurm.schedmd.com/squeue.html
    _STATE_MAP = {
        'BF': JobState.FAILED,
        'CA': JobState.CANCELED,
        'CD': JobState.COMPLETED,
        'CF': JobState.QUEUED,
        'CG': JobState.ACTIVE,
        'DL': JobState.FAILED,
        'F': JobState.FAILED,
        'NF': JobState.FAILED,
        'OOM': JobState.FAILED,
        'PD': JobState.QUEUED,
        'PR': JobState.FAILED,
        'R': JobState.ACTIVE,
        'RD': JobState.QUEUED,
        'RF': JobState.QUEUED,
        'RH': JobState.QUEUED,
        'RQ': JobState.ACTIVE,
        'SO': JobState.ACTIVE,
        'TO': JobState.FAILED,
        # TODO: double-check these
        'RS': JobState.ACTIVE,
        'RV': JobState.QUEUED,
        'SI': JobState.ACTIVE,
        'SE': JobState.ACTIVE,
        'ST': JobState.ACTIVE,
        'S': JobState.ACTIVE
    }

    # see https://slurm.schedmd.com/squeue.html
    _REASONS_MAP = {
        'AssociationJobLimit': 'The job\'s association has reached its maximum job count.',
        'AssociationResourceLimit': 'The job\'s association has reached some resource limit.',
        'AssociationTimeLimit': 'The job\'s association has reached its time limit.',
        'BadConstraints': 'The job\'s constraints can not be satisfied.',
        'BeginTime': 'The job\'s earliest start time has not yet been reached.',
        'Cleaning': 'The job is being requeued and still cleaning up from its previous execution.',
        'Dependency': 'This job is waiting for a dependent job to complete.',
        'FrontEndDown': 'No front end node is available to execute this job.',
        'InactiveLimit': 'The job reached the system InactiveLimit.',
        'InvalidAccount': 'The job\'s account is invalid.',
        'InvalidQOS': 'The job\'s QOS is invalid.',
        'JobHeldAdmin': 'The job is held by a system administrator.',
        'JobHeldUser': 'The job is held by the user.',
        'JobLaunchFailure': 'The job could not be launched.This may be due to a file system '
                            'problem, invalid program name, etc.',
        'Licenses': 'The job is waiting for a license.',
        'NodeDown': 'A node required by the job is down.',
        'NonZeroExitCode': 'The job terminated with a non-zero exit code.',
        'PartitionDown': 'The partition required by this job is in a DOWN state.',
        'PartitionInactive': 'The partition required by this job is in an Inactive state and not '
                             'able to start jobs.',
        'PartitionNodeLimit': 'The number of nodes required by this job is outside of its '
                              'partition\'s current limits. Can also indicate that required nodes '
                              'are DOWN or DRAINED.',
        'PartitionTimeLimit': 'The job\'s time limit exceeds its partition\'s current time limit.',
        'Priority': 'One or more higher priority jobs exist for this partition or advanced '
                    'reservation.',
        'Prolog': 'Its PrologSlurmctld program is still running.',
        'QOSJobLimit': 'The job\'s QOS has reached its maximum job count.',
        'QOSResourceLimit': 'The job\'s QOS has reached some resource limit.',
        'QOSTimeLimit': 'The job\'s QOS has reached its time limit.',
        'ReqNodeNotAvail': 'Some node specifically required by the job is not currently available. '
                           'The node may currently be in use, reserved for another job, in an '
                           'advanced reservation, DOWN, DRAINED, or not responding. Nodes which '
                           'are DOWN, DRAINED, or not responding will be identified as part of '
                           'the job\'s "reason" field as "UnavailableNodes". Such nodes will '
                           'typically require the intervention of a system administrator to make '
                           'available.',
        'Reservation': 'The job is waiting its advanced reservation to become available.',
        'Resources': 'The job is waiting for resources to become available.',
        'SystemFailure': 'Failure of the Slurm system, a file system, the network, etc.',
        'TimeLimit': 'The job exhausted its time limit.',
        'QOSUsageThreshold': 'Required QOS threshold has been breached.',
        'WaitingForScheduling': 'No reason has been set for this job yet. Waiting for the '
                                'scheduler to determine the appropriate reason.'
    }

    def __init__(self, url: Optional[str] = None, config: Optional[SlurmExecutorConfig] = None):
        """
        Parameters
        ----------
        url
            Not used, but required by the spec for automatic initialization.
        config
            An optional configuration for this executor.
        """
        if not config:
            config = SlurmExecutorConfig()
        super().__init__(config=config)
        self.generator = TemplatedScriptGenerator(config, Path(__file__).parent / 'slurm'
                                                  / 'slurm.mustache')

    def generate_submit_script(self, job: Job, context: Dict[str, object],
                               submit_file: IO[str]) -> None:
        """See :meth:`~.BatchSchedulerExecutor.generate_submit_script`."""
        self.generator.generate_submit_script(job, context, submit_file)

    def get_submit_command(self, job: Job, submit_file_path: Path) -> List[str]:
        """See :meth:`~.BatchSchedulerExecutor.get_submit_command`."""
        return ['sbatch', str(submit_file_path.absolute())]

    def get_cancel_command(self, native_id: str) -> List[str]:
        """See :meth:`~.BatchSchedulerExecutor.get_cancel_command`."""
        return ['scancel', '-Q', native_id]

    def process_cancel_command_output(self, exit_code: int, out: str) -> None:
        """See :meth:`~.BatchSchedulerExecutor.process_cancel_command_output`."""
        raise SubmitException('Failed job cancel job: %s' % out)

    def get_hold_command(self, native_id: str) -> List[str]:
        """See :meth:`~.BatchSchedulerExecutor.get_hold_command`."""
        return ['scontrol', 'hold', native_id]

    def process_hold_command_output(self, exit_code: int, out: str) -> str:
        """See :meth:`~.BatchSchedulerExecutor.process_hold_command_output`."""
        if exit_code != 0:
            raise SubmitException('Failed job hold: %s' % out)
        return out

    def get_release_command(self, native_id: str) -> List[str]:
        """See :meth:`~.BatchSchedulerExecutor.get_release_command`."""
        return ['scontrol', 'release', native_id]

    def process_release_command_output(self, exit_code: int, out: str) -> str:
        """See :meth:`~.BatchSchedulerExecutor.process_release_command_output`."""
        if exit_code != 0:
            raise SubmitException('Failed job release: %s' % out)
        return out

    def get_status_command(self, native_ids: Collection[str]) -> List[str]:
        """See :meth:`~.BatchSchedulerExecutor.get_status_command`."""
        # we're not really using job arrays, so this is equivalent to the job ID. However, if
        # we were to use arrays, this would return one ID for the entire array rather than
        # listing each element of the array independently
        return [_SQUEUE_COMMAND, '-O', 'JobArrayID,StateCompact,Reason', '-t', 'all', '--me']

    def parse_status_output(self, exit_code: int, out: str) -> Dict[str, JobStatus]:
        """See :meth:`~.BatchSchedulerExecutor.parse_status_output`."""
        check_status_exit_code(_SQUEUE_COMMAND, exit_code, out)
        r = {}
        lines = iter(out.split('\n'))
        # skip header
        lines.__next__()
        for line in lines:
            if not line:
                continue
            cols = line.split()
            assert len(cols) == 3
            native_id = cols[0]
            state = self._get_state(cols[1])
            msg = self._get_message(cols[2]) if state == JobState.FAILED else None
            r[native_id] = JobStatus(state, message=msg)

        return r

    def get_list_command(self) -> List[str]:
        """See :meth:`~.BatchSchedulerExecutor.get_list_command`."""
        return ['squeue', '--me', '-o', '%i', '-h', '-r', '-t', 'all']

    def _get_state(self, state: str) -> JobState:
        assert state in SlurmJobExecutor._STATE_MAP
        return SlurmJobExecutor._STATE_MAP[state]

    def _get_message(self, reason: str) -> str:
        assert reason in SlurmJobExecutor._REASONS_MAP
        return SlurmJobExecutor._REASONS_MAP[reason]

    def job_id_from_submit_output(self, out: str) -> str:
        """See :meth:`~.BatchSchedulerExecutor.job_id_from_submit_output`."""
        return out.strip().split()[-1]

    def _format_duration(self, d: timedelta) -> str:
        # https://slurm.schedmd.com/sbatch.html#OPT_time:
        #   Acceptable time formats include "minutes", "minutes:seconds", "hours:minutes:seconds",
        #   "days-hours", "days-hours:minutes" and "days-hours:minutes:seconds".
        days = ''
        if d.days > 0:
            days = str(d.days) + '-'
        return days + "%s:%s:%s" % (d.seconds // 3600, (d.seconds // 60) % 60, d.seconds % 60)

    def _clean_submit_script(self, job: Job) -> None:
        super()._clean_submit_script(job)
        self._delete_aux_file(job, '.nodefile')

    def get_info_command(self, native_ids: Optional[List[str]] = None,
                         owner: Optional[str] = None) -> List[str]:
        """See :meth:`~.BatchSchedulerExecutor.get_info_command`."""
        args = [_SQUEUE_COMMAND, '-ho', '%A %a %C %l %j %M %P %t %V %Z %S %u %N']

        # Create commna-separated list of job IDs.
        if native_ids is not None and len(native_ids) > 0:
            jobids = ""
            for id in native_ids:
                if len(id) == 0:
                    continue
                if jobids is None:
                    jobids = id
                else:
                    jobids += ',' + id
            args.append('--job')
            args.append(jobids)

        if owner is not None:
            args.append('--user')
            args.append(owner)

        return args

    def _parse_nodes(self, node_list: str, cpu_per_node: int) -> List[Dict[str, Union[str, int]]]:
        """
        Parse the node list of squeue, and return a list of dictionaries with
        node names and CPU counts.
        """
        result: List[Dict[str, Union[str, int]]] = []
        for match in re.findall(r'([^,\[]+)(?:\[([^\]]+)\])?', str(node_list)):
            prefix, range_str = match
            if range_str:
                for x in range_str.split(","):
                    if re.match(r'^(\d+)-(\d+)$', x):
                        match = re.match(r'^(\d+)-(\d+)$', x)
                        if match is not None:
                            start, end = map(int, match.groups())
                            range_values = range(start, end + 1)
                            result.extend({"name": prefix + str(n),
                                           "procs": cpu_per_node} for n in range_values)
                    else:
                        result.append({"name": prefix + x, "procs": cpu_per_node})
            elif prefix:
                result.append({"name": prefix, "procs": cpu_per_node})
        return result

    def _parse_duration(self, duration: str) -> timedelta:
        """Parse the duration string of squeue, and return a timedelta object."""
        #   Acceptable time formats include "minutes", "minutes:seconds", "hours:minutes:seconds",
        #   "days-hours", "days-hours:minutes" and "days-hours:minutes:seconds".
        #   The default time format is "minutes:seconds".
        if '-' in duration:
            days, time = duration.split('-')
            days_val = int(days)
            hours, minutes, seconds = map(int, time.split(':'))
            return timedelta(days=days_val, hours=hours, minutes=minutes, seconds=seconds)
        else:
            time_parts = duration.split(':')
            if len(time_parts) == 1:
                minutes = int(time_parts[0])
                return timedelta(minutes=minutes)
            elif len(time_parts) == 2:
                minutes, seconds = map(int, time_parts)
                return timedelta(minutes=minutes, seconds=seconds)
            elif len(time_parts) == 3:
                hours, minutes, seconds = map(int, time_parts)
                return timedelta(hours=hours, minutes=minutes, seconds=seconds)
            else:
                raise ValueError(f"Invalid duration format: {duration}")

    def parse_info_command_output(self, exit_code: int, out: str,
                                  jobs: Optional[List[Job]] = None) -> List[Job]:
        """See :meth:`~.BatchSchedulerExecutor.parse_info_output`."""
        check_status_exit_code(_SQUEUE_COMMAND, exit_code, out)
        """ Output of example: Spaces added for clarity.
            $ squeue -o "%A %a %C %l %j %M %P %t %V %Z %S %u %B %N"
        cols[0]   [1]     [2]  [3]        [4]    [5]    [6]       [7]   [8]
            JOBID ACCOUNT CPUS TIME_LIMIT NAME   TIME   PARTITION ST    SUBMIT_TIME
            1418  (null)  1    UNLIMITED  sbatch 0:00   aaa       PD    2025-03-31T13:07:28
            1424  (null)  1    UNLIMITED  sbatch 0:08   aaa       R     2025-04-07T11:34:38
            [9]        [10]                [11] [12]      [13]
            WORK_DIR   START_TIME          USER EXEC_HOST NODELIST
            /home/XYZ  N/A                 XYZ  N/A       n/a
            /home/XYZ  2025-04-07T11:34:38 XYZ  ehost     ehost
            """
        lines = iter(out.split('\n'))
        job_list = []
        for line in lines:
            if not line:
                continue
            cols = line.split()
            assert len(cols) > 10
            native_id = cols[0]
            # Search the job which have native id.
            job = None
            if jobs is not None:
                for job in jobs:
                    if job.native_id == native_id:
                        break
            if job is None:
                # Create a new job object
                spec = JobSpec()
                job = Job(spec=spec)

            if job.executor is None:
                job.executor = self

            if job.spec is None:
                job.spec = JobSpec()

            job._native_id = native_id
            spec = job.spec
            if cols[1] != "(null)":
                spec.attributes.account = cols[1]
            else:
                spec.attributes.account = None
            if spec.resources is None:
                spec.resources = ResourceSpecV1(process_count=int(cols[2]))
            elif isinstance(spec.resources, ResourceSpecV1):
                spec.resources.process_count = int(cols[2])
            if cols[3] == "UNLIMITED":
                spec.attributes.duration = timedelta(seconds=0)
            else:
                spec.attributes.duration = self._parse_duration(cols[3])
            spec.name = cols[4]
            job.current_info.wall_time = int(self._parse_duration(cols[5]).total_seconds())
            spec.attributes.queue_name = cols[6]
            job.status.state = self._get_state(cols[7])
            job.current_info.submission_time = datetime.fromisoformat(cols[8])
            spec.directory = Path(cols[9])
            if cols[10] == "N/A":
                job.current_info.dispatch_time = None
            else:
                job.current_info.dispatch_time = datetime.fromisoformat(cols[10])
            job.current_info.owner = cols[11]
            job.current_info.resourcelist = []
            if len(cols) > 12:
                job.current_info.resourcelist = self._parse_nodes(cols[12], int(cols[2]))

            job.current_info.submit_host = None  # Can not get submit host from squeue
            job.current_info.cpu_time = None     # Can not get CPU time from squeue

            job_list.append(job)

        return job_list
