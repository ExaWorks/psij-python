import logging
import subprocess
import time
import traceback
from abc import abstractmethod
from pathlib import Path
from threading import Thread, RLock
from typing import Optional, List, Dict, Collection, cast, TextIO

from psij import JobExecutor, JobExecutorConfig, Launcher, Job, SubmitException, \
    JobStatus, JobState
from psij.executors.batch.template_function_library import ALL as FUNCTION_LIBRARY


logger = logging.getLogger(__name__)


class BatchSchedulerExecutorConfig(JobExecutorConfig):
    """A base configuration class for :class:`~BatchSchedulerExecutor` implementations.

    When subclassing :class:`~BatchSchedulerExecutor`, specific configuration classes inheriting
    from this class should be defined, even if empty.
    """

    DEFAULT_WORK_DIRECTORY = Path.home() / '.psij' / 'work'

    def __init__(self, launcher_log_file: Optional[Path] = None,
                 work_directory: Optional[Path] = None, queue_polling_interval: int = 30,
                 queue_polling_error_threshold: int = 2,
                 keep_files: bool = False):
        """Initializes a base batch scheduler executor configuration.

        Parameters
        ----------
        launcher_log_file
            See :func:`~JobExecutorConfig.__init__`.
        work_directory
            A directory where submit scripts and auxiliary job files will be generated. In a,
            cluster this directory needs to point to a directory on a shared filesystem. This is so
            that the exit code file, likely written on a service node, can be accessed by PSI/J,
            likely running on a head node.
        queue_polling_interval
            an interval, in seconds, at which the batch scheduler queue will be polled for updates
            to jobs.
        queue_polling_error_threshold
            The number of times consecutive queue polls have to fail in order for the executor to
            report them as job failures.
        keep_files
            Whether to keep submit files and auxiliary job files (exit code and output files) after
            a job has completed.
        """
        super().__init__(launcher_log_file)
        if work_directory:
            self.work_directory = work_directory
        else:
            self.work_directory = BatchSchedulerExecutorConfig.DEFAULT_WORK_DIRECTORY
        self.queue_polling_interval = queue_polling_interval
        self.queue_polling_error_threshold = queue_polling_error_threshold
        self.keep_files = keep_files


class BatchSchedulerExecutor(JobExecutor):
    """A base class for batch scheduler executors.

    This class implements a generic :class:`~JobExecutor` that interacts with batch schedulers.
    There are two main components to the executor: job submission and queue polling. Submission
    is implemented by generating a submit script which is then fed to the queuing system submit
    command.

    The submit script is generated using a :func:`~generate_submit_script`. An implementation of
    this functionality based on Mustache/Pystache (see https://mustache.github.io/ and
    https://pypi.org/project/pystache/) exists in :class:`~TemplatedScriptGenerator`. This class
    can be instantiated by concrete implementations of a batch scheduler executor and the submit
    script generation can be delegated to that instance, which has a method whose signature matches
    that of :func:`~generate_submit_script`. Besides an opened file which points to where the
    contents of the submit script are to be written, the parameters to
    :func:`~generate_submit_script` are the :class:`~Job` that is being submitted and a `context`,
    which is a dictionary with the following structure:
        {
            'job': <the job being submitted>
            'psij': {
                'lib': <dict; function library>,
                'launch_command': <str; launch command>,
                'script_dir': <str; directory where the submit script is generated>
            }
        }

    The *script directory* is a directory (typically `~/.psij/work`) where submit scripts are
    written; it is also used for auxiliary files, such as the *exit code file* (see below) or the
    *script output file*.

    The *launch command* is a list of strings which the script generator should render as the
    command to execute. It wraps the job executable in the proper :class:`~Launcher`.

    The function library is a dictionary mapping function names to functions for all public
    functions in the :mod:`~template_function_library` module.

    The submit script *must* perform two essential actions:
        1. redirect the output of the executable part of the script to the *script output file*,
        which is a file in `<script_dir>` named `<native_id>.out`, where `<native_id>` is the id
        given to the job by the queuing system.
        2. store the exit code of the launch command in the *exit code file* named
        `<native_id>.ec`, also inside `<script_dir>`.

    Once the submit script is generated, the executor renders the submit command using
    :func:`~get_submit_command` and executes it. Its output is then parsed using
    :func:`~job_id_from_submit_output` to retrieve the `native_id` of the job. Subsequently, the
    job is registered with the queue polling thread.

    The queue polling thread regularly polls the batch scheduler queue for updates to job states.
    It builds the command for polling the queue using :func:`~get_status_command`, which takes a
    list of `native_id` strings corresponding to all registered jobs. Implementations are
    strongly encouraged to restrict the query of job states to the specified jobs in order to reduce
    the load on the queuing system. The output of the status command is then parsed using
    :func:`~parse_status_output` and the status of each job is updated accordingly. If the status
    of a registered job is not found in the ouput of the queue status command, it is assumed
    completed (or failed, depending on its exit code), since most queuing systems automatically
    purge completed jobs from their databases after a short period of time. The exit code is read
    from the exit code file, as described above. If the exit code value is not zero, the job is
    assumed failed and an attempt is made to read an error message from the *script output file*.
    """

    def __init__(self, url: Optional[str] = None,
                 config: Optional[BatchSchedulerExecutorConfig] = None):
        """Initializes a `BatchSchedulerExecutor`.

        Parameters
        ----------
        url
            An optional URL pointing to a specific backend
        config
            An configuration for this executor instance; if none is specified, a default
            configuration is used.
        """
        super().__init__(url=url, config=config if config else BatchSchedulerExecutorConfig())
        assert config
        self.work_directory = config.work_directory / self.name
        self._queue_poll_thread = self._start_queue_poll_thread()

    def _ensure_work_dir(self) -> None:
        self.work_directory.mkdir(parents=True, exist_ok=True)

    def submit(self, job: Job) -> None:
        """See :func:`~JobExecutor.submit`."""
        logger.info('Job %s: submitting', job.id)
        self._ensure_work_dir()
        assert (job.spec)

        context = self._create_script_context(job)

        # assumes job ids are unique
        submit_file_path = self.work_directory / (job.id + '.job')
        with submit_file_path.open('w') as submit_file:
            self.generate_submit_script(job, context, submit_file)
        try:
            logger.debug('Job %s: running submit command', job.id)
            out = self._run_command(self.get_submit_command(job, submit_file_path))
            logger.debug('Job %s: submit command ouput: %s', job.id, out)
            job._native_id = self.job_id_from_submit_output(out)
            logger.info('Job %s: native id: %s', job.id, job.native_id)
            self._set_job_status(job, JobStatus(JobState.QUEUED,
                                                metadata={'native_id': job.native_id}))
        except subprocess.CalledProcessError as ex:
            raise SubmitException(ex.output) from None

        self._queue_poll_thread.register_job(job)

    def _get_launcher_from_job(self, job: Job) -> Launcher:
        assert(job.spec)
        launcher_name = job.spec.launcher
        if not launcher_name:
            launcher_name = Launcher.DEFAULT_LAUNCHER_NAME
        return self._get_launcher(launcher_name)

    def cancel(self, job: Job) -> None:
        """Cancels a job if it has not otherwise completed.

        A command is constructed using :func:`~get_cancel_command` and executed in order to cancel
        the job. Also see :func:`~JobExecutor.cancel`.
        """
        if job.native_id is None:
            raise SubmitException('Job does not have a native ID.')
        if job.status.state.final:
            return
        try:
            self._run_command(self.get_cancel_command(job.native_id))
        except subprocess.CalledProcessError as ex:
            if job.status.state.final and not job.status.state == JobState.CANCELED:
                # assume that the queuing system failed to cancel the job because it was already
                # completed instead of raising an exception; in any event, there is nothing to
                # gain from canceling a completed job since cancelation is assumed to mean that
                # the job should not be running any more, a condition already met by the completion
                return
            raise SubmitException(ex.output)

    def attach(self, job: Job, native_id: str) -> None:
        """Attaches a job to a native job.

        Attempts to connect `job` to a native job with `native_id` such that the job correctly
        reflects updates to the status of the native job. If the native job was previously
        submitted using this executor (hence having an *exit code file* and a *script output file*),
        the executor will attempt to retrieve the exit code and errors from the job. Otherwise, it
        may be impossible for the executor to distinguish between a failed and successfully
        completed job.

        Parameters
        ----------
        job
            The PSI/J job to attach.
        native_id
            The id of the batch scheduler job to attach to.
        """
        job._native_id = native_id
        self._queue_poll_thread.register_job(job)

    @abstractmethod
    def generate_submit_script(self, job: Job, context: Dict[str, object],
                               submit_file: TextIO) -> None:
        """Called to generate a submit script for a job.

        Concrete implementations of batch scheduler executors must override this method in
        order to generate a submit script for a job.

        Parameters
        ----------
        job
            The job to be submitted.
        context
            A dictionary containing information about the context in which the job is being
            submitted. For details, see the description of this class.
        submit_file
            An opened file-like object to which the contents of the submit script should be
            written.
        """
        pass

    @abstractmethod
    def get_submit_command(self, job: Job, submit_file_path: Path) -> List[str]:
        """Constructs a command to submit a job to a batch scheduler.

        Concrete implementations of batch scheduler executors must override this method.

        Parameters
        ----------
        job
            The job being submitted.
        submit_file_path
            The path to a submit script generated using :func:`~generate_submit_script`.

        Returns
        -------
        A list of strings representing the command and arguments to execute in order to submit
        the job, such as `['qsub', str(submit_file_path)]`.
        """
        pass

    @abstractmethod
    def job_id_from_submit_output(self, out: str) -> str:
        """Extracts a native job id from the output of the submit command.

        Concrete implementations of batch scheduler executors must override this method. This
        method is only invoked if the submit command completes with a zero exit code, so
        implementations of this method do not need to determine whether the output reflects an
        error from the submit command.

        Parameters
        ----------
        out
            The output from the submit command.

        Returns
        -------
        A string representing the native id of the newly submitted job.
        """
        pass

    @abstractmethod
    def get_cancel_command(self, native_id: str) -> List[str]:
        """Constructs a command to cancel a batch scheduler job.

        Concrete implementations of batch scheduler executors must override this method.

        Parameters
        ----------
        native_id
            The native id of the job being cancelled.

        Returns
        -------
        A list of strings representing the command and arguments to execute in order to cancel
        the job, such as, e.g., `['qdel', native_id]`.
        """
        pass

    @abstractmethod
    def get_status_command(self, native_ids: Collection[str]) -> List[str]:
        """Constructs a command to retrieve the status of a list of jobs.

        Concrete implementations of batch scheduler executors must override this method. In order
        to prevent overloading the queueing system, concrete implementations are strongly
        encouraged to return a command that only queries for the status of the indicated jobs. The
        command returned by this method should produce an output that is understood by
        :func:`~parse_status_output`.

        Parameters
        ----------
        jobs
            A collection of native ids corresponding to the jobs whose status is sought.

        Returns
        -------
        A list of strings representing the command and arguments to execute in order to get the
        status of the jobs.
        """
        pass

    @abstractmethod
    def parse_status_output(self, out: str) -> Dict[str, JobStatus]:
        """Parses the output of a job status command.

        Concrete implementations of batch scheduler executors must override this method. The output
        is meant to have been produced by the command generated by :func:`~get_status_command`.

        Parameters
        ----------
        out
            The string output of the status command as prescribed by :func:`~get_status_command`.
        Returns
        -------
        A dictionary mapping native job ids to :class:`~JobStatus` objects. The implementation of
        this method need not process the *exit code file* or the *script output file* since it is
        done by the base `BatchSchedulerExecutor` implementation.
        """
        pass

    def _create_script_context(self, job: Job) -> Dict[str, object]:
        launcher = self._get_launcher_from_job(job)
        ctx = {
            'job': job,
            'psij': {
                'lib': FUNCTION_LIBRARY,
                'launch_command': launcher.get_launch_command(job),
                'script_dir': str(self.work_directory)
            }
        }
        return ctx

    def _run_command(self, cmd: List[str]) -> str:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode > 0:
            msg = ''
            if res.stdout:
                msg += res.stdout
            if res.stderr:
                if msg != '':
                    msg += '\n'
                msg += res.stderr
            if msg == '':
                msg = 'Unknown error'
            raise subprocess.CalledProcessError(res.returncode, cmd, output=msg)
        else:
            return res.stdout

    def _start_queue_poll_thread(self) -> '_QueuePollThread':
        qp_thread = _QueuePollThread(self.name + ' Queue Polling Thread',
                                     cast(BatchSchedulerExecutorConfig, self.config), self)
        qp_thread.start()
        return qp_thread

    def _set_job_status(self, job: Job, status: JobStatus) -> None:
        if status.state.is_greater_than(job.status.state) is False:
            # is_greater_than returns T/F if the states are comparable and None if not, so
            # we have to check explicitly for the boolean value rather than truthiness
            return
        if status.state.final and job.native_id:
            self._clean_submit_script(job)
            self._read_aux_files(job, status)
        super()._set_job_status(job, status)

    def _clean_submit_script(self, job: Job) -> None:
        try:
            assert isinstance(self.config, BatchSchedulerExecutorConfig)
            if not self.config.keep_files:
                submit_file_path = self.work_directory / (job.id + '.job')
                submit_file_path.unlink()
        except Exception as ex:
            logger.warning('Job %s: failed to read auxiliary files: %s' % (job.id, ex))

    def _read_aux_files(self, job: Job, status: JobStatus) -> None:
        try:
            # read exit code and output files
            exit_code_str = self._read_aux_file(job, '.ec')
            if exit_code_str:
                status.exit_code = int(exit_code_str)
                if status.exit_code != 0:
                    status.state = JobState.FAILED
            if status.state == JobState.FAILED:
                if status.message is None:
                    # only read output from submit script if another error message is not
                    # already present
                    status.message = self._read_aux_file(job, '.out')
            else:
                self._delete_aux_file(job, '.out')

        except Exception as ex:
            logger.warning('Job %s: failed to read auxiliary files: %s' % (job.id, ex))

    def _read_aux_file(self, job: Job, suffix: str) -> Optional[str]:
        assert job.native_id
        path = self.work_directory / (job.native_id + suffix)
        if path.exists():
            try:
                with open(path) as f:
                    return f.read()
            finally:
                assert isinstance(self.config, BatchSchedulerExecutorConfig)
                if not self.config.keep_files:
                    path.unlink()
        else:
            return None

    def _delete_aux_file(self, job: Job, suffix: str) -> None:
        assert job.native_id
        path = self.work_directory / (job.native_id + suffix)
        if path.exists():
            path.unlink()

    def list(self) -> List[str]:
        """Returns a list of jobs known to the underlying implementation.

        See :func:`~JobExecutor.list`.
        The returned list is a list of `native_id` strings representing jobs known to the
        underlying batch scheduler implementation, whether submitted through this executor or not.
        Implementations are encouraged to restrict the results to jobs accessible by the current
        user.
        """
        pass


class _QueuePollThread(Thread):
    def __init__(self, name: str, config: BatchSchedulerExecutorConfig,
                 executor: BatchSchedulerExecutor):
        super().__init__()
        self.name = name
        self.daemon = True
        self.config = config
        self.executor = executor
        # native_id -> job
        self._jobs = {}  # type: Dict[str, List[Job]]
        # counts consecutive errors while invoking qstat or equivalent
        self._poll_error_count = 0
        self._jobs_lock = RLock()

    def run(self) -> None:
        logger.debug('Executor %s: queue poll thread started', self.executor)
        while True:
            self._poll()
            time.sleep(self.config.queue_polling_interval)

    def _poll(self) -> None:
        with self._jobs_lock:
            if len(self._jobs) == 0:
                return
            jobs_copy = dict(self._jobs)
        logger.info('Polling for %s jobs', len(jobs_copy))
        try:
            out = self.executor._run_command(self.executor.get_status_command(jobs_copy.keys()))
            logger.debug('Output from qstat: %s', out)
            self._poll_error_count = 0

            status_map = self.executor.parse_status_output(out)

            for native_id, job_list in jobs_copy.items():
                try:
                    status = self._get_job_status(native_id, status_map)
                except Exception:
                    status = JobStatus(JobState.FAILED,
                                       message='Failed to update job status: %s' %
                                               traceback.format_exc())
                for job in job_list:
                    self.executor._set_job_status(job, status)
                if status.state.final:
                    with self._jobs_lock:
                        del self._jobs[native_id]
        except subprocess.CalledProcessError as ex:
            self._handle_poll_error(False, ex, 'Failed to poll for job status. '
                                               'Error from status command: {}'.format(ex.output))
        except Exception as ex:
            msg = traceback.format_exc()
            self._handle_poll_error(True, ex, 'Failed to poll for job status. '
                                              'Internal error: {}'.format(msg))

    def _get_job_status(self, native_id: str, status_map: Dict[str, JobStatus]) -> JobStatus:
        if native_id in status_map:
            return status_map[native_id]
        else:
            return JobStatus(JobState.COMPLETED)

    def _handle_poll_error(self, immediate: bool, ex: Exception, msg: str) -> None:
        logger.warning('Polling error: %s', msg)
        self._poll_error_count += 1
        if immediate or (self._poll_error_count > self.config.queue_polling_error_threshold):
            self._poll_error_count = 0
            # fail all jobs
            with self._jobs_lock:
                # We should only poll if there is at least one job, so we should not be in a
                # situation when we polled and there were no jobs to poll for
                # Internal errors are a bit different, since they could, in principle, occur
                # after the last job was processed and removed from self._jobs; in practice,
                # the code in _poll has the job removal from _jobs as the last possible step
                assert len(self._jobs) > 0
                jobs_copy = dict(self._jobs)
                self._jobs.clear()
            for job_list in jobs_copy.values():
                for job in job_list:
                    self.executor._set_job_status(job, JobStatus(JobState.FAILED, message=msg))

    def register_job(self, job: Job) -> None:
        assert job.native_id
        logger.info('Job %s: registering', job.id)
        with self._jobs_lock:
            native_id = job.native_id
            if native_id not in self._jobs:
                self._jobs[native_id] = [job]
            self._jobs[job.native_id].append(job)
