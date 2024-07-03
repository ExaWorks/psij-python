from datetime import timedelta
from pathlib import Path
from typing import Optional, Collection, List, Dict, IO

from psij import Job, JobStatus, JobState, SubmitException
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
