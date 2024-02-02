"""This module contains the local :class:`~psij.JobExecutor`."""
import logging
import os
import pathlib
import platform
import shlex
import shutil
import signal
import subprocess
import threading
import time
from abc import abstractmethod
from tempfile import mkstemp
from typing import Optional, Dict, List, Tuple, TypeVar, Set, Callable

import psutil
from psutil import NoSuchProcess

from psij import InvalidJobException, SubmitException, ResourceSpecV1
from psij import Job, JobSpec, JobExecutorConfig, JobState, JobStatus
from psij import JobExecutor
from psij.exceptions import CompositeException, LauncherException, JobException
from psij.staging import StageIn, StagingMode, StageOut, StageOutFlags

logger = logging.getLogger(__name__)


def _format_shell_cmd(args: List[str]) -> str:
    """Formats an argument list in a way that allows it to be pasted in a shell."""
    cmd = ''
    for arg in args:
        cmd += shlex.quote(arg)
        cmd += ' '
    return cmd


class _JobThread(threading.Thread):
    def __init__(self, job: Job, executor: JobExecutor) -> None:
        super().__init__(name = 'LocalJobThread-' + job.id)
        self.executor = executor
        self.cancel_flag = False

    @abstractmethod
    def cancel(self):
        pass

    def _get_state_from_ec(self, ec: int) -> Tuple[JobState, Optional[Exception]]:
        if ec is None or ec == 0:
            return JobState.COMPLETED, None
        elif ec < 0:
            if self.cancel_flag:
                return JobState.CANCELED, None
            else:
                return JobState.FAILED, JobException(ec)
        else:
            # ec > 0
            # It is not quite clear what happens in Windows. Windows allows the user
            # to specify an exit code when killing a process, exit code which will become
            # the exit code of the terminated process. However, psutil does not specify what
            # is being done for that on Windows. The psutil sources suggest that signal.SIGTERM
            # is used, so we check for that.
            if platform.system() == 'Windows' and ec == signal.SIGTERM and self.cancel_flag:
                return JobState.CANCELED, None
            else:
                return JobState.FAILED, JobException(ec)


# The addition of file staging makes fully asynchronous job management difficult, since we don't
# really have much in the way of something reasonably supporting true async file copying. So since
# we have to use threads anyway, and since the local executor is not really meant to scale, we use
# them for attached processes also.
class _AttachedJobThread(_JobThread):
    def __init__(self, job: Job, pid: int, executor: JobExecutor) -> None:
        super().__init__(job, executor)
        self.job = job
        self.pid = pid
        self._attach()

    def _attach(self):
        with self.job._status_cv:
            try:
                self.process = psutil.Process(self.pid)
            except NoSuchProcess:
                # will check in run() and set status
                self.process = None
            except Exception as ex:
                raise SubmitException('Cannot attach to pid %s' % self.pid, exception=ex)

    def run(self) -> None:
        # We assume that the native_id above is a PID that was obtained at some point using
        # list(). If so, the process is either still running or has completed. Either way, we must
        # bring it up to ACTIVE state
        self.executor._set_job_status(self.job, JobStatus(JobState.QUEUED, time=time.time()))
        self.executor._set_job_status(self.job, JobStatus(JobState.ACTIVE, time=time.time()))
        try:
            self._wait_for_job()
        except Exception:
            pass

    def _wait_for_job(self):
        message = None
        if self.process is None:
            state = JobState.COMPLETED
        else:
            ec = self.process.wait()
            state = self._get_state_from_ec(ec)

            if state == JobState.FAILED:
                message = 'Job failed with exit code %s' % ec

        self.executor._set_job_status(self.job, JobStatus(state, message=message, time=time.time()))

    def cancel(self):
        with self.job._status_cv:
            self.cancel_flag = True
            if self.process:
                self.process.kill()


class _JobCanceled(Exception):
    pass


T = TypeVar('T')


class _ChildJobThread(_JobThread):

    FLAG_MAP = {JobState.COMPLETED: StageOutFlags.ON_SUCCESS,
                JobState.FAILED: StageOutFlags.ON_ERROR,
                JobState.CANCELED: StageOutFlags.ON_CANCEL}

    def __init__(self, job: Job, spec: JobSpec, executor: JobExecutor) -> None:
        super().__init__(job, executor)
        self.job = job
        self.spec = spec
        if spec.directory is None:
            self.jobdir = pathlib.Path('/tmp')
        else:
            self.jobdir = spec.directory
        self.state = None
        # set for any error; the overall job is automatically considered failed if set
        self.exception = None
        self.exit_code = None
        self.process = None

    def run(self):
        # The following workflow is based on the idea that no error should go unreported. The
        # flow is as follows:
        # - if there is an error in staging, fail immediately (i.e., do not perform cleanup or
        # any other steps).
        # - if there is an internal error (i.e., not an executable failure), treat as above and
        # fail immediately
        # - if a job is canceled during stage in, clean up. If there is an error in cleanup,
        # the job will fail instead.
        # - if a job is canceled while running, stage out and clean up. If there is an error in
        # stage out and/or cleanup, the job will instead fail.
        # - if the job fails and there is a subsequent error in staging or cleanup, a compound
        # error is created
        # - cancellation is ignored during and after stageout

        try:
            try:
                self.stage_in()
                self.run_job()
                self.stage_out()
            except _JobCanceled:
                # only stage_in and run_job (but before the job is actually started)
                # are allowed to raise _JobCanceled
                self.state = JobState.CANCELED
            self.cleanup()
        except Exception as ex:
            self.fail_job(ex)

        self.update_job_status()

    def update_job_status(self):
        if self.exception:
            self.executor._set_job_status(self.job,
                                          JobStatus(JobState.FAILED, time=time.time(),
                                                    message=str(self.exception),
                                                    metadata={'exception': self.exception},
                                                    exit_code=self.exit_code))
        else:
            # failed without an exception set is not allowed
            assert self.state != JobState.FAILED
            self.executor._set_job_status(self.job, JobStatus(self.state, time=time.time()))

    def fail_job(self, ex: Exception) -> None:
        if self.state == JobState.FAILED:
            if self.exception is None:
                self.exception = ex
            else:
                if not isinstance(self.exception, CompositeException):
                    self.exception = CompositeException(self.exception)
                self.exception.add_exception(ex)
        else:
            self.state = JobState.FAILED
            self.exception = ex

    def stage_in(self) -> None:
        self.executor._set_job_status(self.job, JobStatus(JobState.STAGE_IN, time=time.time()))
        self._map(self._stage_in_one, self.spec.stage_in)

    def stage_out(self):
        self.executor._set_job_status(self.job, JobStatus(JobState.STAGE_OUT, time=time.time()))
        self._map(self._stage_out_one, self.spec.stage_out)

    def cleanup(self):
        self.executor._set_job_status(self.job, JobStatus(JobState.CLEANUP, time=time.time()))
        self._map(self._cleanup_one, self.spec.cleanup)

    @staticmethod
    def _map(fn: Callable[[T], None], s: Optional[Set[T]], ) -> None:
        if s is None:
            return
        for o in s:
            fn(o)

    def _stage_in_one(self, stage_in: StageIn) -> None:
        if self.cancel_flag:
            raise _JobCanceled()
        src = stage_in.source
        scheme = src.scheme
        if scheme == '':
            scheme = 'file'
        if scheme == 'file':
            self._local_copy(pathlib.Path(src.path), self._job_rel(stage_in.target),
                             stage_in.mode, False)
        else:
            self.fail_job(ValueError('Unsupported scheme "%s" for %s' % (scheme, src)))

    def _stage_out_one(self, stage_out: StageOut) -> None:
        dst = stage_out.target
        scheme = dst.scheme
        if scheme == '':
            scheme = 'file'
        if scheme == 'file':
            flags = stage_out.flags
            state = _ChildJobThread.FLAG_MAP[self.state]
            if state in flags:
                self._local_copy(self._job_rel(stage_out.source), pathlib.Path(dst.path),
                                 stage_out.mode, StageOutFlags.IF_PRESENT in stage_out.flags)
        else:
            self.fail_job(ValueError('Unsupported scheme "%s" for %s' % (scheme, dst)))

    def _cleanup_one(self, cleanup: pathlib.Path) -> None:
        # do some sanity checks
        cleanup = self._job_rel(cleanup)
        if cleanup.samefile(pathlib.Path('/')):
            raise ValueError('Refusing to clean root directory.')
        if cleanup.samefile(pathlib.Path.home()):
            raise ValueError('Refusing to clean user home directory.')
        if cleanup.is_dir():
            shutil.rmtree(str(cleanup))
        else:
            cleanup.unlink(missing_ok=True)

    def _job_rel(self, path: pathlib.Path) -> pathlib.Path:
        path = path.expanduser()
        if not path.is_absolute():
            path = self.jobdir / path
        return path.absolute()

    def _local_copy(self, source: pathlib.Path, target: pathlib.Path, mode: StagingMode,
                    if_present=False):
        if if_present and not os.path.exists(source):
            return
        if mode == StagingMode.COPY:
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy(source, target)
        elif mode == StagingMode.MOVE:
            shutil.move(source, target)
        elif mode == StagingMode.LINK:
            os.symlink(source, target)

    def run_job(self):
        launcher = self.executor._get_launcher(self._get_launcher_name(self.spec))
        args = launcher.get_launch_command(self.job)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('Running %s', _format_shell_cmd(args))
        nodefile = self._generate_nodefile(self.job)
        try:
            env = _get_env(self.spec, nodefile)
            with self.job._status_cv:
                if self.cancel_flag:
                    raise _JobCanceled()
                self.process = subprocess.Popen(args, stdout=subprocess.PIPE,
                                                stderr=subprocess.STDOUT, close_fds=True,
                                                cwd=self.spec.directory, env=env)
            self.job._native_id = self.process.pid
            self.executor._set_job_status(self.job,
                                          JobStatus(JobState.ACTIVE, time=time.time(),
                                                    metadata={'nativeId': self.job._native_id}))
            self.exit_code = self.process.wait()

            # We want to capture errors in the launcher scripts. Since, under normal circumstances,
            # the exit code of the launcher is the exit code of the job, we must use a different
            # mechanism to distinguish between job errors and launcher errors. So we delegate to
            # the launcher implementation to figure out if the error belongs to the job or not
            if self.process.stdout:
                out = self.process.stdout.read().decode('utf-8')
            else:
                out = None
            if out and launcher.is_launcher_failure(out):
                message = self.process.launcher.get_launcher_failure_message(out)
                self.fail_job(LauncherException(message))
            else:
                self.state, self.exception = self._get_state_from_ec(self.exit_code)
        finally:
            if nodefile:
                os.remove(nodefile)

    def cancel(self):
        with self.job._status_cv:
            self.cancel_flag = True
            if self.process is not None:
                self.process.kill()

    def _generate_nodefile(self, job: Job) -> Optional[str]:
        assert job.spec is not None
        if job.spec.resources is None:
            return None
        if job.spec.resources.version == 1:
            assert isinstance(job.spec.resources, ResourceSpecV1)
            n = job.spec.resources.computed_process_count
            if n == 1:
                # as a bit of an optimization, we don't generate a nodefile when doing "single
                # node" jobs on local.
                return None
            (file, nodefile) = mkstemp(suffix='.nodelist')
            for i in range(n):
                os.write(file, 'localhost\n'.encode())
            os.close(file)
            return nodefile
        else:
            raise SubmitException('Cannot handle resource specification with version %s'
                                  % job.spec.resources.version)

    def _get_launcher_name(self, spec: JobSpec) -> str:
        if spec.launcher is None:
            return 'single'
        else:
            return spec.launcher


def _get_env(spec: JobSpec, nodefile: Optional[str]) -> Optional[Dict[str, str]]:
    env: Optional[Dict[str, str]] = None
    if spec.inherit_environment:
        if spec.environment is None and nodefile is None:
            # if env is none in Popen, it inherits env from parent
            return None
        else:
            # merge current env with spec env
            env = os.environ.copy()
            if spec.environment:
                env.update(spec.environment)
            if nodefile is not None:
                env['PSIJ_NODEFILE'] = nodefile
            return env
    else:
        # only spec env
        if nodefile is None:
            env = spec.environment
        else:
            env = {'PSIJ_NODEFILE': nodefile}
            if spec.environment:
                env.update(spec.environment)

        return env


class LocalJobExecutor(JobExecutor):
    """
    A job executor that runs jobs locally using :class:`subprocess.Popen`.

    This job executor is intended to be used either to run jobs directly on the same machine as the
    PSI/J library or for testing purposes.

    .. note::
        In Linux, attached jobs always appear to complete with a zero exit code regardless
        of the actual exit code.
    .. warning::
        Instantiation of a local executor from both parent process and a `fork()`-ed process
        is not guaranteed to work. In general, using `fork()` and multi-threading in Linux is
        unsafe, as suggested by the `fork()` man page. While PSI/J attempts to minimize problems
        that can arise when `fork()` is combined with threads (which are used by PSI/J), no
        guarantees can be made and the chances of unexpected behavior are high. Please do not use
        PSI/J with `fork()`. If you do, please be mindful that support for using PSI/J with
        `fork()` will be limited.
    """

    def __init__(self, url: Optional[str] = None,
                 config: Optional[JobExecutorConfig] = None) -> None:
        """
        :param url: Not used, but required by the spec for automatic initialization.
        :param config: The `LocalJobExecutor` does not have any configuration options.
        :type config: psij.JobExecutorConfig
        """
        super().__init__(url=url, config=config if config else JobExecutorConfig())
        self._threads_lock = threading.RLock()
        self.threads: Dict[str, _JobThread] = {}

    def submit(self, job: Job) -> None:
        """
        Submits the specified :class:`~psij.Job` to be run locally.

        Successful return of this method indicates that the job has been started locally and all
        changes in the job status, including failures, are reported using notifications. If the job
        specification is invalid, an :class:`~psij.InvalidJobException` is thrown. If
        the actual submission fails for reasons outside the validity of the job,
        a :class:`~psij.SubmitException` is thrown.

        :param job: The job to be submitted.
        """
        spec = self._check_job(job)

        self._set_job_status(job, JobStatus(JobState.QUEUED, time=time.time()))

        with job._status_cv:
            if job.status.state == JobState.CANCELED:
                raise SubmitException('Job canceled')
            job_thread = _ChildJobThread(job, spec, self)

        with self._threads_lock:
            self.threads[job.id] = job_thread
            job_thread.start()

    def cancel(self, job: Job) -> None:
        """
        Cancels a job.

        :param job: The job to cancel.
        """

        with self._threads_lock:
            try:
                job_thread = self.threads[job.id]
            except KeyError:
                raise ValueError('The job %s is not managed by this executor.' % job.id)
        with job._status_cv:
            if job_thread is not None:
                job_thread.cancel()
            else:
                self._set_job_status(job, JobStatus(JobState.CANCELED))

    def list(self) -> List[str]:
        """
        Return a list of ids representing jobs that are running on the underlying implementation.

        Specifically for the `LocalJobExecutor`, this returns a list of `~psij.NativeId` objects
        corresponding to the processes running under the current user on the local machine. These
        processes need not correspond to jobs statrted by calling the `submit()` method of an
        instance of a `LocalJobExecutor`.

        :return: The list of `~psij.NativeId` objects corresponding to the current user's
            processes running locally.
        """
        my_username = psutil.Process().username()
        return [str(p.pid) for p in psutil.process_iter(['pid', 'username'])
                if p.info['username'] == my_username]

    def attach(self, job: Job, native_id: str) -> None:
        """
        Attaches a job to a process.

        The job must be in the :attr:`~psij.JobState.NEW` state. The exit code of the attached job
        will not be available upon completion and a zero exit code will always be returned for jobs
        attached by the `LocalJobExecutor`.

        :param job: The job to attach.
        :param native_id: The native ID of the process to attached to, as obtained through
            :func:`~psij.executors.LocalJobExecutor.list` method.
        """
        if job.status.state != JobState.NEW:
            raise InvalidJobException('Job must be in the NEW state')
        job.executor = self
        pid = int(native_id)

        with job._status_cv:
            if job.status.state == JobState.CANCELED:
                raise SubmitException('Job canceled')
            job_thread = _AttachedJobThread(job, pid, self)

        with self._threads_lock:
            self.threads[job.id] = job_thread
            job_thread.start()
