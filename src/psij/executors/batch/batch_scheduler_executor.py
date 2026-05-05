import asyncio
import logging
import os

import subprocess
from asyncio import AbstractEventLoop

import time
import traceback
import weakref
from abc import abstractmethod, ABC
from aiofile import async_open
from datetime import timedelta
from pathlib import Path
from threading import Thread, RLock
from typing import Optional, List, Dict, Collection, cast, Union, Set, Tuple, Generator, \
    Iterable, Type

from psij._async import set_job_status
from psij._base_executor import BaseExecutor
from psij.base_job import BaseJob
from psij.launchers.script_based_launcher import ScriptBasedLauncher

from psij import JobExecutor, JobExecutorConfig, Launcher, Job, SubmitException, \
    JobStatus, JobState, AsyncJob, AsyncJobExecutor
from psij.executors.batch.template_function_library import ALL as FUNCTION_LIBRARY
from psij.utils import _StatusUpdater, _FileCleaner

UNKNOWN_ERROR = 'PSIJ: Unknown error'

logger = logging.getLogger(__name__)


def check_status_exit_code(command: str, exit_code: int, out: str) -> None:
    """Check if exit_code is nonzero and, if so, raise a RuntimeError.

    This function produces a somewhat user-friendly exception message that combines
    the command that was run with its output.

    Parameters
    ----------
    command
        The command that was run. This is only used to format the error message.
    exit_code
        The exit code returned by running the ``command``.
    out:
        The output produced by ``command``.
    """
    if exit_code != 0:
        raise RuntimeError(f'status command {command!r} exited '
                           f'with {exit_code} and output {out!r}')


def _attrs_to_mustache(job: BaseJob) -> Dict[str, Union[object, List[Dict[str, object]]]]:
    assert job.spec is not None
    if not job.spec.attributes or not job.spec.attributes._custom_attributes:
        return {}

    r: Dict[str, Union[object, List[Dict[str, object]]]] = {}

    for k, v in job.spec.attributes._custom_attributes.items():
        ks = k.split('.', maxsplit=1)
        if len(ks) == 2:
            # always use lower case here
            ks[0] = ks[0].lower()
            if ks[0] not in r:
                r[ks[0]] = []
            cast(List[Dict[str, object]], r[ks[0]]).append({'key': ks[1], 'value': v})
        else:
            r[k] = v
    return r


def _env_to_mustache(job: BaseJob) -> List[Dict[str, str]]:
    assert job.spec is not None
    if not job.spec.environment:
        return []

    r = []
    for k, v in job.spec.environment.items():
        r.append({'name': k, 'value': v})
    return r


def _process_cmd_out(cmd: List[str], returncode: Optional[int], out: str) -> str:
    assert returncode is not None
    if returncode != 0:
        if out:
            msg = out
        else:
            msg = UNKNOWN_ERROR
        raise subprocess.CalledProcessError(returncode, cmd, output=msg)
    else:
        return out


def _run_command(cmd: List[str]) -> str:
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return _process_cmd_out(cmd, res.returncode, res.stdout)


async def _async_run_command(cmd: List[str]) -> str:
    p = await asyncio.create_subprocess_exec(*cmd,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT,
                                             close_fds=True)
    (out, _) = await p.communicate()
    return _process_cmd_out(cmd, p.returncode, out.decode())


class BatchSchedulerExecutorConfig(JobExecutorConfig):
    """A base configuration class for :class:`~BatchSchedulerExecutor` implementations.

    When subclassing :class:`~BatchSchedulerExecutor`, specific configuration classes inheriting
    from this class should be defined, even if empty.
    """

    def __init__(self, launcher_log_file: Optional[Path] = None,
                 work_directory: Optional[Path] = None, queue_polling_interval: int = 30,
                 initial_queue_polling_delay: int = 2,
                 queue_polling_error_threshold: int = 2,
                 keep_files: bool = False):
        """
        Parameters
        ----------
        launcher_log_file
            See :class:`~psij.JobExecutorConfig`.
        work_directory
            See :class:`~psij.JobExecutorConfig`.
        queue_polling_interval
            an interval, in seconds, at which the batch scheduler queue will be polled for updates
            to jobs.
        initial_queue_polling_delay
            the time to wait before polling the queue for the first time; for quick tests that only
            submit a short job that completes nearly instantly or for jobs that fail very quickly,
            this can dramatically reduce the time taken to get the necessary job status update.
        queue_polling_error_threshold
            The number of times consecutive queue polls have to fail in order for the executor to
            report them as job failures.
        keep_files
            Whether to keep submit files and auxiliary job files (exit code and output files) after
            a job has completed.
        """
        super().__init__(launcher_log_file, work_directory)
        self.queue_polling_interval = queue_polling_interval
        self.initial_queue_polling_delay = initial_queue_polling_delay
        self.queue_polling_error_threshold = queue_polling_error_threshold
        self.keep_files = keep_files
        if 'PSIJ_BATCH_KEEP_FILES' in os.environ:
            self.keep_files = True

    @classmethod
    def _from_config(cls, config: JobExecutorConfig) -> 'BatchSchedulerExecutorConfig':
        new = cls()
        new.work_directory = config.work_directory
        new.launcher_log_file = config.launcher_log_file
        return new


class InvalidJobStateError(Exception):
    """An exception that signals that a job cannot be cancelled due to it being already done."""

    pass


class BatchScheduler(ABC):
    """An abstract representation of a batch scheduler.

    Concrete instances of this class can be used together with the
    :class:`~.BatchSchedulerExecutor` class to implement executors for typical batch scheduler
    that use qsub/qstat style commands.
    """

    @abstractmethod
    def __init__(self, config: BatchSchedulerExecutorConfig) -> None:
        """
        Parameters
        ----------
        config
            A batch scheduler configuration.
        """
        # only here for the signature
        pass

    @abstractmethod
    def generate_submit_script(self, job: BaseJob, context: Dict[str, object]) -> Iterable[str]:
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

        Returns
        -------
        An iterable with the submit script contents split into one or more consecutive chunks.
        """
        pass

    @abstractmethod
    def get_submit_command(self, job: BaseJob, submit_file_path: Path) -> List[str]:
        """Constructs a command to submit a job to a batch scheduler.

        Concrete implementations of batch scheduler executors must override this method.

        Parameters
        ----------
        job
            The job being submitted.
        submit_file_path
            The path to a submit script generated using :meth:`~generate_submit_script`.

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
    def process_cancel_command_output(self, exit_code: int, out: str) -> None:
        """Handle output from a failed cancel command.

        The main purpose of this method is to help distinguish between the cancel command
        failing due to an invalid job state (such as the job having completed before the cancel
        command was invoked) and other types of errors. Since job state errors are ignored, there
        are two options:

        1. Instruct the cancel command to not fail on invalid state errors and have this
        method always raise a :class:`~psij.exceptions.SubmitException`, since it is only invoked
        on "other" errors.

        2. Have the cancel command fail on both invalid state errors and other errors and
        interpret the output from the cancel command to distinguish between the two and raise
        the appropriate exception.

        Parameters
        ----------
        exit_code
            The exit code from the cancel command.
        out
            The output from the cancel command.

        Raises
        ------
        InvalidJobStateError
            Raised if the job cancellation has failed because the job was in a completed or failed
            state at the time when the cancellation command was invoked.
        SubmitException
            Raised for all other reasons.
        """
        pass

    @abstractmethod
    def get_status_command(self, native_ids: Collection[str]) -> List[str]:
        """Constructs a command to retrieve the status of a list of jobs.

        Concrete implementations of batch scheduler executors must override this method. In order
        to prevent overloading the queueing system, concrete implementations are strongly
        encouraged to return a command that only queries for the status of the indicated jobs. The
        command returned by this method should produce an output that is understood by
        :meth:`~parse_status_output`.

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
    def parse_status_output(self, exit_code: int, out: str) -> Dict[str, JobStatus]:
        """Parses the output of a job status command.

        Concrete implementations of batch scheduler executors must override this method. The output
        is meant to have been produced by the command generated by :meth:`~get_status_command`.

        Parameters
        ----------
        out
            The string output of the status command as prescribed by :meth:`~get_status_command`.
        Returns
        -------
        A dictionary mapping native job ids to :class:`~psij.JobStatus` objects. The
        implementation of this method need not process the *exit code file* or the *script
        output file* since it is done by the base `BatchSchedulerExecutor` implementation.
        """
        pass

    @abstractmethod
    def get_list_command(self) -> List[str]:
        """Constructs a command to retrieve the list of jobs known to the LRM for the current user.

        Concrete implementations of batch scheduler executors must override this method. Upon
        running the command, the output can be parsed with :meth:`~parse_list_output`.

        Returns
        -------
        A list of strings representing the executable and arguments to invoke in order to obtain
        the list of jobs the LRM knows for the current user.
        """
        pass

    def parse_list_output(self, out: str) -> List[str]:
        """Parses the output of the command obtained from :meth:`~get_list_command`.

        The default implementation of this method assumes that the output has no header and
        consists of native IDs, one per line, possibly surrounded by whitespace. Concrete
        implementations should override this method if a different format is expected.

        Parameters
        ----------
        out
            The output from the "list" command as returned by :meth:`~get_list_command`.
        Returns
        -------
        A list of strings representing the native IDs of the jobs known to the LRM for the current
        user.
        """
        return [s.strip() for s in out.splitlines()]

    def _current_user(self) -> str:
        return os.getlogin()

    def _format_duration(self, d: timedelta) -> str:
        # the default is hh:mm:ss, with hh not limited to 24; this is the least ambiguous
        # choice
        return '%s:%s:%s' % (int(d.total_seconds()) // 3600, (d.seconds // 60) % 60, d.seconds % 60)


class BatchSchedulerExecutor(BaseExecutor):
    """A base class for batch scheduler executors.

    This class implements a generic :class:`~.BaseExecutor` that interacts with batch
    schedulers. It implements functionality that is common to both synchronous
    (:class:`~psij.JobExecutor`) and asynchronous (:class:`~psij.AsyncJobExecutor`). Specialized
    versions (:class:`~.SyncBatchSchedulerExecutor` and :class:`~.AsyncBatchSchedulerExecutor`)
    implement the synchronous and asynchronous functionality, respectively. Concrete
    implementations that intend to use the infrastructure provided by :class:`~.BatchScheduler` and
    :class:`~.BatchSchedulerExecutor` should implement a concrete subclass of
    :class:`~.BatchScheduler` and then subclass :class:`~.SyncBatchSchedulerExecutor` and
    :class:`~.AsyncBatchSchedulerExecutor`: to provide implementations for the
    :meth:`~.BatchSchedulerExecutor.get_concrete_classes` method, which should return a tuple of
    the concrete BatchScheduler class and configuration class (which can be the base
    :class:`~.BatchSchedulerExecutorConfig`):

        class MyBatchScheduler(BatchScheduler):
            ...

        class MySyncBatchExecutor(SyncBatchSchedulerExecutor):

            def get_concrete_classes(self) \
                -> Tuple[Type[BatchScheduler], Type[BatchSchedulerExecutorConfig]]:
            return MyBatchScheduler, MyExecutorConfig

        class MyAsyncBatchExecutor(AsyncBatchSchedulerExecutor):

            def get_concrete_classes(self) \
                -> Tuple[Type[BatchScheduler], Type[BatchSchedulerExecutorConfig]]:
            return MyBatchScheduler, MyExecutorConfig

    There are two main components to an executor: job submission and queue polling. Submission
    is implemented by generating a submit script which is then fed to the queuing system submit
    command.

    The submit script is generated using :meth:`~.BatchScheduler.generate_submit_script`. An
    implementation of this functionality based on Mustache/Pystache (see
    https://mustache.github.io/ and https://pypi.org/project/pystache/) exists in
    :class:`~.TemplatedScriptGenerator`. This class can be instantiated by concrete implementations
    of a batch scheduler executor and the submit script generation can be delegated to the
    :meth:`~.TemplatedScriptGenerator.render` method of that instance, a method which returns a
    ``Iterable[str]`` whose items, when concatenated, produce the rendered submit script. The
    parameters to :meth:`~~.BatchScheduler.generate_submit_script` are the :class:`~psij.Job`
    instance that is being submitted and a `context`, which is a dictionary with the following
    structure::

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
    command to execute. It wraps the job executable in the proper :class:`~psij.Launcher`.

    The function library is a dictionary mapping function names to functions for all public
    functions in the :mod:`~.template_function_library` module.

    The submit script *must* perform two essential actions:

        1. redirect the output of the executable part of the script to the *script output file*,
        which is a file in `<script_dir>` named `<native_id>.out`, where `<native_id>` is the id
        given to the job by the queuing system.

        2. store the exit code of the launch command in the *exit code file* named
        `<native_id>.ec`, also inside `<script_dir>`.

    Additionally, where appropriate, the submit script should set the environment variable named
    ``PSIJ_NODEFILE`` to point to a file containing a list of nodes that are allocated for the job,
    one per line, with a total number of lines matching the process count of the job.

    Once the submit script is generated, the executor renders the submit command using
    :meth:`~~.BatchScheduler.get_submit_command` and executes it. Its output is then parsed using
    :meth:`~~.BatchScheduler.job_id_from_submit_output` to retrieve the `native_id` of the job.
    Subsequently, the job is registered with the queue polling thread.

    The queue polling thread regularly polls the batch scheduler queue for updates to job states.
    It builds the command for polling the queue using :meth:`~~.BatchScheduler.get_status_command`,
    which takes a list of `native_id` strings corresponding to all registered jobs. Implementations
    are strongly encouraged to restrict the query of job states to the specified jobs in order to
    reduce the load on the queuing system. The output of the status command is then parsed using
    :meth:`~~.BatchScheduler.parse_status_output` and the status of each job is updated accordingly.
    If the status of a registered job is not found in the output of the queue status command, it is
    assumed completed (or failed, depending on its exit code), since most queuing systems
    automatically purge completed jobs from their databases after a short period of time. The exit
    code is read from the exit code file, as described above. If the exit code value is not zero,
    the job is assumed failed and an attempt is made to read an error message from the *script
    output file*.
    """

    def __init__(self, url: Optional[str], config: Optional[BatchSchedulerExecutorConfig] = None):
        """
        Parameters
        ----------
        url
            An optional URL pointing to a specific backend. Not used by batch scheduler
            executors.
        config
            An configuration for this executor instance; if none is specified, a default
            configuration is used.
        """
        sched_cls, config_cls = self.get_concrete_classes()
        config = self._get_config(config, config_cls)
        super().__init__(config=config)
        self.sched = sched_cls(config)
        assert config
        self._queue_poll_thread = self._start_queue_poll_thread()
        self.work_directory = config.work_directory / self.name
        self.work_directory.mkdir(parents=True, exist_ok=True)
        cast(_FileCleaner, _FileCleaner.get_instance()).clean(self.work_directory)

    @abstractmethod
    def get_concrete_classes(self) \
            -> Tuple[Type[BatchScheduler], Type[BatchSchedulerExecutorConfig]]:
        """Gets the concrete classes for this executor.

        This method must be overridden by concrete implementations of
        :class:`~.SyncBatchSchedulerExecutor` and :class:`~.AsyncBatchSchedulerExecutor`
        to return classes of the concrete implementations of the corresponding
        :class:`~.BatchScheduler` and :class:`~.BatchSchedulerExecutorConfig`

        Returns
        -------
            A tuple of classes (MyBatchScheduler, MyBatchSchedulerExecutorConfig).
        """
        pass

    def _get_config(self, config: Optional[JobExecutorConfig],
                    config_cls: Type[BatchSchedulerExecutorConfig]) -> BatchSchedulerExecutorConfig:
        if config is None:
            return config_cls()
        if isinstance(config, BatchSchedulerExecutorConfig):
            return config
        return BatchSchedulerExecutorConfig._from_config(config)

    def _start_queue_poll_thread(self) -> '_QueuePollThread':
        qp_thread = _QueuePollThread(self.name + ' Queue Polling Thread',
                                     cast(BatchSchedulerExecutorConfig, self.config), self)
        qp_thread.start()
        return qp_thread

    def _get_launcher_from_job(self, job: BaseJob) -> Launcher:
        assert job.spec
        launcher_name = job.spec.launcher
        if not launcher_name:
            launcher_name = Launcher.DEFAULT_LAUNCHER_NAME
        return self._get_launcher(launcher_name)

    def _create_script_context(self, job: BaseJob) -> Dict[str, object]:
        launcher = self._get_launcher_from_job(job)
        if isinstance(launcher, ScriptBasedLauncher) and logger.isEnabledFor(logging.DEBUG):
            log_file = str((self.work_directory / (job.id + '_launcher.log')).absolute())
            launch_command = launcher.get_launch_command(job, log_file=log_file)
        else:
            launch_command = launcher.get_launch_command(job)
        logger.debug('Launch command: %s', launch_command)

        ctx = {
            'job': job,
            'custom_attributes': _attrs_to_mustache(job),
            'env': _env_to_mustache(job),
            'psij': {
                'lib': FUNCTION_LIBRARY,
                'launch_command': launch_command,
                'script_dir': str(self.work_directory),
                'us_file': self._queue_poll_thread.status_updater.update_file_name,
                'us_port': self._queue_poll_thread.status_updater.update_port,
                'us_addrs': ', '.join(self._queue_poll_thread.status_updater.ips)
            }
        }
        assert job.spec is not None
        if job.spec.attributes:
            duration = job.spec.attributes.duration
            if duration is not None:
                ctx['formatted_job_duration'] = self.sched._format_duration(duration)
        return ctx

    def _clean_submit_script(self, job: BaseJob) -> None:
        try:
            assert isinstance(self.config, BatchSchedulerExecutorConfig)
            if not self.config.keep_files:
                submit_file_path = self.work_directory / (job.id + '.job')
                try:
                    submit_file_path.unlink()
                except FileNotFoundError:
                    # this can reasonably happen for attached jobs when the main
                    # job cleans up the script instead
                    pass
        except Exception as ex:
            logger.warning('Job %s: failed clean submit script: %s', job.id, ex)

    def _aux_file_path(self, job: BaseJob, suffix: str) -> Path:
        assert job
        assert job.native_id
        assert suffix
        return self.work_directory / (job.native_id + suffix)

    def _read_aux_files_gen(self, job: BaseJob, status: JobStatus) \
            -> Generator[Path, Union[str, None], None]:
        try:
            if logger.isEnabledFor(logging.DEBUG):
                launcher_log = yield self.work_directory / (job.id + '_launcher.log')
                if launcher_log is not None:
                    logger.debug('Job %s: launcher log: %s', job.id, launcher_log)
            if status.state == JobState.CANCELED:
                # exit code and other things are not very meaningful for canceled jobs
                return
            # read exit code and output files
            exit_code_str = yield self._aux_file_path(job, '.ec')
            if exit_code_str:
                status.exit_code = int(exit_code_str)
                if status.exit_code != 0:
                    status.state = JobState.FAILED
            if status.state == JobState.FAILED:

                if status.message is None:
                    # only read output from submit script if another error message is not
                    # already present
                    out = yield self._aux_file_path(job, '.out')
                    if out:
                        if '_PSIJ_SCRIPT_DONE' not in out:
                            status.message = out
                    logger.debug('Output from launcher: %s', status.message)
                else:
                    self._delete_aux_file(self._aux_file_path(job, '.out'))

        except Exception as ex:
            logger.warning('Job %s: failed to read auxiliary files: %s', job.id, ex)

    def _delete_aux_file(self, path: Path, force: bool = False) -> None:
        assert isinstance(self.config, BatchSchedulerExecutorConfig)
        if self.config.keep_files:
            return
        if force or path.exists():
            try:
                path.unlink()
            except FileNotFoundError:
                pass  # see above; attached job may race with original job


class _QueuePollThread(Thread):
    def __init__(self, name: str, config: BatchSchedulerExecutorConfig,
                 executor: BatchSchedulerExecutor):
        super().__init__()
        self.name = name
        self.daemon = True
        self.config = config
        self.done = False
        self.executor = weakref.ref(executor, self._stop)
        # native_id -> job
        self._jobs: Dict[str, Set[Tuple[BaseJob, Optional[AbstractEventLoop]]]] = {}
        # counts consecutive errors while invoking qstat or equivalent
        self._poll_error_count = 0
        self._jobs_lock = RLock()
        self.status_updater = cast(_StatusUpdater, _StatusUpdater.get_instance())

    def run(self) -> None:
        logger.debug('Executor %s: queue poll thread started', self.executor)

        time.sleep(self.config.initial_queue_polling_delay)
        while not self.done:
            self._poll()
            start = time.time()
            now = start
            while now - start < self.config.queue_polling_interval:
                time.sleep(1)
                now = time.time()
        logger.info('Thread %s exiting due to executor collection' % self)

    def _stop(self, executor: object) -> None:
        self.done = True

    def _poll(self) -> None:
        executor = self.executor()
        if executor is None:
            return
        with self._jobs_lock:
            if len(self._jobs) == 0:
                return
            jobs_copy = dict(self._jobs)
        logger.info('Polling for %s jobs', len(jobs_copy))
        try:
            out = _run_command(executor.sched.get_status_command(jobs_copy.keys()))
        except subprocess.CalledProcessError as ex:
            out = ex.output
            exit_code = ex.returncode
        except Exception as ex:
            self._handle_poll_error(executor, True, ex,
                                    f'Failed to poll for job status: {traceback.format_exc()}')
            return
        else:
            exit_code = 0
            self._poll_error_count = 0
        logger.debug('Output from status command: %s', out)
        try:
            status_map = executor.sched.parse_status_output(exit_code, out)
        except Exception as ex:
            self._handle_poll_error(executor, False, ex,
                                    f'Failed to poll for job status: {traceback.format_exc()}')
            return
        try:
            for native_id, job_set in jobs_copy.items():
                try:
                    status = self._get_job_status(native_id, status_map)
                except Exception:
                    status = JobStatus(JobState.FAILED,
                                       message='Failed to update job status: %s' %
                                               traceback.format_exc())
                for (job, loop) in job_set:
                    set_job_status(executor, job, status, loop)

        except Exception as ex:
            msg = traceback.format_exc()
            self._handle_poll_error(executor, True, ex, f'Error updating job statuses {msg}')

    def _get_job_status(self, native_id: str, status_map: Dict[str, JobStatus]) -> JobStatus:
        if native_id in status_map:
            return status_map[native_id]
        else:
            return JobStatus(JobState.COMPLETED)

    def _handle_poll_error(self, executor: BatchSchedulerExecutor, immediate: bool, ex: Exception,
                           msg: str) -> None:
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
            for job_set in jobs_copy.values():
                for (job, loop) in job_set:
                    self.unregister_job(job)
                    set_job_status(executor, job,
                                   JobStatus(JobState.FAILED, message=msg), loop)

    def register_job(self, job: BaseJob, loop: Optional[AbstractEventLoop] = None) -> None:
        executor = self.executor()
        if isinstance(job, AsyncJob) and loop is None:
            raise RuntimeError('No loop for async job.')
        # This method is only called from the executor. It stands to reason that the
        # executor cannot have been GC-ed.
        assert executor is not None
        self.status_updater.register_job(job, executor, loop)
        assert job.native_id
        logger.info('Job %s: registering', job.id)
        with self._jobs_lock:
            native_id = job.native_id
            try:
                self._jobs[native_id].add((job, loop))
            except KeyError:
                self._jobs[native_id] = {(job, loop)}

    def unregister_job(self, job: BaseJob) -> None:
        self.status_updater.unregister_job(job)
        assert job.native_id
        logger.info('Job %s: unregistering', job.id)
        with self._jobs_lock:
            native_id = job.native_id
            try:
                del self._jobs[native_id]
            except KeyError:
                # If two or more jobs are attached to the same native ID, the
                # first one being unregistered would already have removed
                # the dict entry
                pass


class SyncBatchSchedulerExecutor(BatchSchedulerExecutor, JobExecutor):
    """A synchronous version of a BatchSchedulerExecutor.

    This class implements a generic synchronous (subclass of :class:`~psij.JobExecutor`) executor
    for batch schedulers.
    """

    def submit(self, job: Job) -> None:
        """See :func:`~psij.JobExecutor.submit`."""
        logger.info('Job %s: submitting', job.id)
        self._check_job(job)

        context = self._create_script_context(job)

        # assumes job ids are unique
        submit_file_path = self.work_directory / (job.id + '.job')
        with submit_file_path.open('w') as submit_file:
            for chunk in self.sched.generate_submit_script(job, context):
                submit_file.write(chunk)
        try:
            logger.debug('Job %s: running submit command', job.id)
            out = _run_command(self.sched.get_submit_command(job, submit_file_path))
            logger.debug('Job %s: submit command output: %s', job.id, out)
            job.native_id = self.sched.job_id_from_submit_output(out)
            logger.info('Job %s: native id: %s', job.id, job.native_id)
            self._set_job_status(job, JobStatus(JobState.QUEUED,
                                                metadata={'native_id': job.native_id}))
        except subprocess.CalledProcessError as ex:
            if logger.isEnabledFor(logging.DEBUG):
                with submit_file_path.open('r') as submit_file:
                    script = submit_file.read()
                logger.debug('Job %s: submit script is: %s' % (job.id, script))

            raise SubmitException(ex.output) from None

        self._queue_poll_thread.register_job(job)

    def cancel(self, job: Job) -> None:
        """Cancels a job if it has not otherwise completed.

        A command is constructed using :meth:`~~.BatchScheduler.get_cancel_command` and executed in
        order to cancel the job. Also see :meth:`~psij.JobExecutor.cancel`.
        """
        if job.native_id is None:
            raise SubmitException('Job does not have a native ID.')
        if job.status.state.final:
            return
        try:
            _run_command(self.sched.get_cancel_command(job.native_id))
        except subprocess.CalledProcessError as ex:
            try:
                self.sched.process_cancel_command_output(ex.returncode, ex.output)
            except InvalidJobStateError:
                # do nothing; the job has completed anyway
                pass
            except SubmitException:
                # re-raise
                raise

    def list(self) -> List[str]:
        """Returns a list of jobs known to the underlying implementation.

        See :meth:`~psij.JobExecutor.list`.
        The returned list is a list of `native_id` strings representing jobs known to the
        underlying batch scheduler implementation, whether submitted through this executor or not.
        Implementations are encouraged to restrict the results to jobs accessible by the current
        user.
        """
        return self.sched.parse_list_output(_run_command(self.sched.get_list_command()))

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
        job.executor = self
        self._queue_poll_thread.register_job(job)

    def disconnect(self, validity: Optional[timedelta] = None) -> str:
        """See :meth:`~.JobExecutor.disconnect`."""
        return 'local'

    def reconnect(self, session: str) -> None:
        """See :meth:`~.JobExecutor.reconnect`."""
        pass

    def _set_job_status(self, job: Job, status: JobStatus) -> None:
        if status.state.is_greater_than(job.status.state) is False:
            # is_greater_than returns T/F if the states are comparable and None if not, so
            # we have to check explicitly for the boolean value rather than truthiness
            return
        if status.state.final:
            self._queue_poll_thread.unregister_job(job)
            if job.native_id:
                self._clean_submit_script(job)
                self._read_aux_files(job, status)
        super()._set_job_status(job, status)

    def _read_aux_file(self, path: Path) -> Optional[str]:
        logger.debug('Attempting to read %s', path)
        if path.exists():
            try:
                with open(path) as f:
                    return f.read()
            finally:
                self._delete_aux_file(path=path, force=True)
        else:
            logger.debug('%s does not exist', path)
            return None

    def _read_aux_files(self, job: Job, status: JobStatus) -> None:
        gen = self._read_aux_files_gen(job, status)
        try:
            path = next(gen)
            while True:
                logger.debug('Got request to read %s', path)
                content = self._read_aux_file(path)
                path = gen.send(content)
        except StopIteration:
            pass


class AsyncBatchSchedulerExecutor(BatchSchedulerExecutor, AsyncJobExecutor):
    """Am asynchronous version of a BatchSchedulerExecutor.

    This class implements a generic asynchronous (subclass of :class:`~psij.AsyncJobExecutor`)
    executor for batch schedulers.
    """

    async def submit(self, job: AsyncJob) -> None:
        """See :func:`~psij.JobExecutor.submit`."""
        logger.info('Job %s: submitting', job.id)
        self._check_job(job)

        context = self._create_script_context(job)

        # assumes job ids are unique
        submit_file_path = self.work_directory / (job.id + '.job')
        async with async_open(submit_file_path, 'w') as submit_file:
            for chunk in self.sched.generate_submit_script(job, context):
                await submit_file.write(chunk)
        try:
            logger.debug('Job %s: running submit command', job.id)
            out = await _async_run_command(self.sched.get_submit_command(job, submit_file_path))
            logger.debug('Job %s: submit command output: %s', job.id, out)
            job.native_id = self.sched.job_id_from_submit_output(out)
            logger.info('Job %s: native id: %s', job.id, job.native_id)
            await self._set_job_status(job, JobStatus(JobState.QUEUED,
                                                      metadata={'native_id': job.native_id}))
        except subprocess.CalledProcessError as ex:
            if logger.isEnabledFor(logging.DEBUG):
                async with async_open(submit_file_path, 'r') as submit_file:
                    script = await submit_file.read()
                logger.debug('Job %s: submit script is: %s' % (job.id, script))

            raise SubmitException(ex.output) from None

        self._queue_poll_thread.register_job(job, asyncio.get_running_loop())

    async def cancel(self, job: AsyncJob) -> None:
        """Cancels a job if it has not otherwise completed.

        A command is constructed using :meth:`~~.BatchScheduler.get_cancel_command` and executed in
        order to cancel the job. Also see :meth:`~psij.JobExecutor.cancel`.
        """
        if job.native_id is None:
            raise SubmitException('Job does not have a native ID.')
        if job.status.state.final:
            return
        try:
            await _async_run_command(self.sched.get_cancel_command(job.native_id))
        except subprocess.CalledProcessError as ex:
            try:
                self.sched.process_cancel_command_output(ex.returncode, ex.output)
            except InvalidJobStateError:
                # do nothing; the job has completed anyway
                pass
            except SubmitException:
                # re-raise
                raise

    async def list(self) -> List[str]:
        """Returns a list of jobs known to the underlying implementation.

        See :meth:`~psij.JobExecutor.list`.
        The returned list is a list of `native_id` strings representing jobs known to the
        underlying batch scheduler implementation, whether submitted through this executor or not.
        Implementations are encouraged to restrict the results to jobs accessible by the current
        user.
        """
        return self.sched.parse_list_output(await _async_run_command(self.sched.get_list_command()))

    async def attach(self, job: AsyncJob, native_id: str) -> None:
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
        job.executor = self
        self._queue_poll_thread.register_job(job, asyncio.get_running_loop())

    async def disconnect(self, validity: Optional[timedelta] = None) -> str:
        """See :meth:`~.JobExecutor.disconnect`."""
        return 'local'

    def reconnect(self, session: str) -> None:
        """See :meth:`~.JobExecutor.reconnect`."""
        pass

    async def _set_job_status(self, job: AsyncJob, status: JobStatus) -> None:
        if status.state.is_greater_than(job.status.state) is False:
            # is_greater_than returns T/F if the states are comparable and None if not, so
            # we have to check explicitly for the boolean value rather than truthiness
            return
        if status.state.final:
            self._queue_poll_thread.unregister_job(job)
            if job.native_id:
                self._clean_submit_script(job)
                await self._read_aux_files(job, status)
        await super()._set_job_status(job, status)

    async def _read_aux_file(self, path: Path) -> Optional[str]:
        logger.debug('Attempting to read %s', path)
        if path.exists():
            try:
                async with async_open(path) as f:
                    return await f.read()  # type: ignore
            finally:
                self._delete_aux_file(path=path, force=True)
        else:
            logger.debug('%s does not exist', path)
            return None

    async def _read_aux_files(self, job: AsyncJob, status: JobStatus) -> None:
        gen = self._read_aux_files_gen(job, status)
        try:
            path = next(gen)
            while True:
                logger.debug('Got request to read %s', path)
                content = await self._read_aux_file(path)
                path = gen.send(content)
                logger.debug(f'Content sent ({content})')
        except StopIteration:
            pass
