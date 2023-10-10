"""This module contains the local :class:`~psij.JobExecutor`."""
import logging
import os
import shlex
import signal
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from tempfile import mkstemp
from types import FrameType
from typing import Optional, Dict, List, Tuple, Type, cast

import psutil

from psij import InvalidJobException, SubmitException, Launcher, ResourceSpecV1
from psij import Job, JobSpec, JobExecutorConfig, JobState, JobStatus
from psij import JobExecutor
from psij.utils import SingletonThread

logger = logging.getLogger(__name__)


def _format_shell_cmd(args: List[str]) -> str:
    """Formats an argument list in a way that allows it to be pasted in a shell."""
    cmd = ''
    for arg in args:
        cmd += shlex.quote(arg)
        cmd += ' '
    return cmd


def _handle_sigchld(signum: int, frame: Optional[FrameType]) -> None:
    _ProcessReaper.get_instance()._handle_sigchld()


if threading.current_thread() != threading.main_thread():
    logger.warning('The psij module is being imported from a non-main thread. This prevents the'
                   'use of signals in the local executor, which will slow things down a bit.')
else:
    signal.signal(signal.SIGCHLD, _handle_sigchld)


_REAPER_SLEEP_TIME = 0.1


class _ProcessEntry(ABC):
    def __init__(self, job: Job, executor: 'LocalJobExecutor', launcher: Optional[Launcher]):
        self.job = job
        self.executor = executor
        self.exit_code: Optional[int] = None
        self.done_time: Optional[float] = None
        self.out: Optional[str] = None
        self.kill_flag = False
        self.process: Optional[subprocess.Popen[bytes]] = None
        self.launcher = launcher

    @abstractmethod
    def kill(self) -> None:
        assert self.process is not None
        root = psutil.Process(self.process.pid)
        for proc in root.children(recursive=True):
            proc.kill()
        self.process.kill()

    @abstractmethod
    def poll(self) -> Tuple[Optional[int], Optional[str]]:
        pass

    def __repr__(self) -> str:
        pid = '-'
        if self.process:
            pid = str(self.process.pid)
        return '{}[jobid: {}, pid: {}]'.format(self.__class__.__name__, self.job.id, pid)


class _ChildProcessEntry(_ProcessEntry):
    def __init__(self, job: Job, executor: 'LocalJobExecutor',
                 launcher: Optional[Launcher]) -> None:
        super().__init__(job, executor, launcher)
        self.nodefile: Optional[str] = None

    def kill(self) -> None:
        super().kill()

    def poll(self) -> Tuple[Optional[int], Optional[str]]:
        assert self.process is not None
        exit_code = self.process.poll()
        if exit_code is not None:
            if self.nodefile:
                os.unlink(self.nodefile)
            if self.process.stdout:
                return exit_code, self.process.stdout.read().decode('utf-8')
            else:
                return exit_code, None
        else:
            return None, None


class _AttachedProcessEntry(_ProcessEntry):
    def __init__(self, job: Job, process: psutil.Process, executor: 'LocalJobExecutor'):
        super().__init__(job, executor, None)
        self.process = process

    def kill(self) -> None:
        super().kill()

    def poll(self) -> Tuple[Optional[int], Optional[str]]:
        try:
            assert self.process
            ec: Optional[int] = self.process.wait(timeout=0)
            if ec is None:
                return 0, None
            else:
                return ec, None
        except psutil.TimeoutExpired:
            return None, None


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


class _ProcessReaper(SingletonThread):

    @classmethod
    def get_instance(cls: Type['_ProcessReaper']) -> '_ProcessReaper':
        return cast('_ProcessReaper', super().get_instance())

    def __init__(self) -> None:
        super().__init__(name='Local Executor Process Reaper', daemon=True)
        self._jobs: Dict[Job, _ProcessEntry] = {}
        self._lock = threading.RLock()
        self._cvar = threading.Condition()

    def register(self, entry: _ProcessEntry) -> None:
        logger.debug('Registering process %s', entry)
        with self._lock:
            self._jobs[entry.job] = entry

    def run(self) -> None:
        logger.debug('Started {}'.format(self))
        done: List[_ProcessEntry] = []
        while True:
            with self._lock:
                for entry in done:
                    del self._jobs[entry.job]
                jobs = dict(self._jobs)
            try:
                done = self._check_processes(jobs)
            except Exception as ex:
                logger.error('Error polling for process status', ex)
            with self._cvar:
                self._cvar.wait(_REAPER_SLEEP_TIME)

    def _handle_sigchld(self) -> None:
        with self._cvar:
            try:
                self._cvar.notify_all()
            except RuntimeError:
                # In what looks like rare cases, notify_all(), seemingly when combined with
                # signal handling, raises `RuntimeError: release unlocked lock`.
                # There appears to be an unresolved Python bug about this:
                #    https://bugs.python.org/issue34486
                # We catch the exception here and log it. It is hard to tell if that will not lead
                # to further issues. It would seem like it shouldn't: after all, all we're doing is
                # making sure we don't sleep too much, but, even if we do, the consequence is a
                # small delay in processing a completed job. However, since this exception seems
                # to be a logical impossibility when looking at the code in threading.Condition,
                # there is really no telling what else could go wrong.
                logger.debug('Exception in Condition.notify_all()')

    def _check_processes(self, jobs: Dict[Job, _ProcessEntry]) -> List[_ProcessEntry]:
        done: List[_ProcessEntry] = []

        for entry in jobs.values():
            if entry.kill_flag:
                entry.kill()

            exit_code, out = entry.poll()
            if exit_code is not None:
                entry.exit_code = exit_code
                entry.done_time = time.time()
                entry.out = out
                done.append(entry)

        for entry in done:
            entry.executor._process_done(entry)

        return done

    def cancel(self, job: Job) -> None:
        with self._lock:
            p = self._jobs[job]
            p.kill_flag = True


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
        self._reaper = _ProcessReaper.get_instance()

    def _generate_nodefile(self, job: Job, p: _ChildProcessEntry) -> Optional[str]:
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
            (file, p.nodefile) = mkstemp(suffix='.nodelist')
            for i in range(n):
                os.write(file, 'localhost\n'.encode())
            os.close(file)
            return p.nodefile
        else:
            raise SubmitException('Cannot handle resource specification with version %s'
                                  % job.spec.resources.version)

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

        p = _ChildProcessEntry(job, self, self._get_launcher(self._get_launcher_name(spec)))
        assert p.launcher
        args = p.launcher.get_launch_command(job)

        try:
            with job._status_cv:
                if job.status.state == JobState.CANCELED:
                    raise SubmitException('Job canceled')
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('Running %s', _format_shell_cmd(args))
            nodefile = self._generate_nodefile(job, p)
            env = _get_env(spec, nodefile)
            p.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         close_fds=True, cwd=spec.directory, env=env)
            self._reaper.register(p)
            job._native_id = p.process.pid
            self._set_job_status(job, JobStatus(JobState.QUEUED, time=time.time(),
                                                metadata={'nativeId': job._native_id}))
            self._set_job_status(job, JobStatus(JobState.ACTIVE, time=time.time()))
        except Exception as ex:
            raise SubmitException('Failed to submit job', exception=ex)

    def cancel(self, job: Job) -> None:
        """
        Cancels a job.

        :param job: The job to cancel.
        """
        self._set_job_status(job, JobStatus(JobState.CANCELED))
        self._reaper.cancel(job)

    def _process_done(self, p: _ProcessEntry) -> None:
        assert p.exit_code is not None
        message = None
        if p.exit_code == 0:
            state = JobState.COMPLETED
        elif p.exit_code < 0 and p.kill_flag:
            state = JobState.CANCELED
        else:
            # We want to capture errors in the launcher scripts. Since, under normal circumstances,
            # the exit code of the launcher is the exit code of the job, we must use a different
            # mechanism to distinguish between job errors and launcher errors. So we delegate to
            # the launcher implementation to figure out if the error belongs to the job or not
            if p.launcher and p.out and p.launcher.is_launcher_failure(p.out):
                message = p.launcher.get_launcher_failure_message(p.out)
            state = JobState.FAILED

        self._set_job_status(p.job, JobStatus(state, time=p.done_time, exit_code=p.exit_code,
                                              message=message))

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

        self._reaper.register(_AttachedProcessEntry(job, psutil.Process(pid), self))
        # We assume that the native_id above is a PID that was obtained at some point using
        # list(). If so, the process is either still running or has completed. Either way, we must
        # bring it up to ACTIVE state
        self._set_job_status(job, JobStatus(JobState.QUEUED, time=time.time()))
        self._set_job_status(job, JobStatus(JobState.ACTIVE, time=time.time()))

    def _get_launcher_name(self, spec: JobSpec) -> str:
        if spec.launcher is None:
            return 'single'
        else:
            return spec.launcher
