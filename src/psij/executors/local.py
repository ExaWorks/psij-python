"""This module contains the local :class:`~psij.JobExecutor`."""
import logging
import os
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from distutils.version import StrictVersion
from typing import Optional, Dict, List, Type, Tuple

import psutil

from psij import InvalidJobException, SubmitException, Launcher
from psij import Job, JobSpec, JobExecutorConfig, JobState, JobStatus
from psij import JobExecutor

logger = logging.getLogger(__name__)


_REAPER_SLEEP_TIME = 0.2


class _ProcessEntry(ABC):
    def __init__(self, job: Job, executor: 'LocalJobExecutor', launcher: Optional[Launcher]):
        self.job = job
        self.executor = executor
        self.exit_code = None  # type: Optional[int]
        self.done_time = None  # type: Optional[float]
        self.out = None  # type: Optional[str]
        self.kill_flag = False
        self.process = None  # type: Optional[subprocess.Popen[bytes]]
        self.launcher = launcher

    @abstractmethod
    def kill(self) -> None:
        pass

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

    def kill(self) -> None:
        assert self.process is not None
        self.process.kill()

    def poll(self) -> Tuple[Optional[int], Optional[str]]:
        assert self.process is not None
        exit_code = self.process.poll()
        if exit_code is not None:
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
        assert self.process
        self.process.kill()

    def poll(self) -> Tuple[Optional[int], Optional[str]]:
        try:
            assert self.process
            ec = self.process.wait(timeout=0)  # type: Optional[int]
            if ec is None:
                return 0, None
            else:
                return ec, None
        except psutil.TimeoutExpired:
            return None, None


def _get_env(spec: JobSpec) -> Optional[Dict[str, str]]:
    if spec.inherit_environment:
        if not spec.environment:
            # if env is none in Popen, it inherits env from parent
            return None
        else:
            # merge current env with spec env
            env = os.environ.copy()
            env.update(spec.environment)
            return env
    else:
        # only spec env
        return spec.environment


class _ProcessReaper(threading.Thread):
    _instance = None  # type: _ProcessReaper
    _lock = threading.RLock()

    @classmethod
    def get_instance(cls: Type['_ProcessReaper']) -> '_ProcessReaper':
        with cls._lock:
            if cls._instance is None:
                cls._instance = _ProcessReaper()
                cls._instance.start()
            return cls._instance

    def __init__(self) -> None:
        super().__init__(name='Local Executor Process Reaper', daemon=True)
        self._jobs = {}  # type: Dict[Job, _ProcessEntry]
        self._lock = threading.RLock()

    def register(self, entry: _ProcessEntry) -> None:
        logger.debug('Registering process %s', entry)
        with self._lock:
            self._jobs[entry.job] = entry

    def run(self) -> None:
        logger.debug('Started {}'.format(self))
        while True:
            with self._lock:
                try:
                    self._check_processes()
                except Exception as ex:
                    logger.error('Error polling for process status', ex)
            time.sleep(_REAPER_SLEEP_TIME)

    def _check_processes(self) -> None:
        done = []  # type: List[_ProcessEntry]
        for entry in self._jobs.values():
            if entry.kill_flag:
                entry.kill()

            exit_code, out = entry.poll()
            if exit_code is not None:
                entry.exit_code = exit_code
                entry.done_time = time.time()
                entry.out = out
                done.append(entry)
        for entry in done:
            del self._jobs[entry.job]
            entry.executor._process_done(entry)

    def cancel(self, job: Job) -> None:
        with self._lock:
            p = self._jobs[job]
            p.kill_flag = True


class LocalJobExecutor(JobExecutor):
    """
    A job executor that runs jobs locally using :func:`popen`.

    Limitations: in Linux, attached jobs always appear to complete with a zero exit code regardless
    of the actual exit code.
    """

    _NAME_ = 'local'
    _VERSION_ = StrictVersion('0.0.1')

    def __init__(self, url: Optional[str] = None,
                 config: Optional[JobExecutorConfig] = None) -> None:
        """
        Initializes a `LocalJobExecutor`.

        :param url: Not used, but required by the spec for automatic initialization.
        :param config: The `LocalJobExecutor` does not have any configuration options.
        :type config: psij.JobExecutorConfig
        """
        super().__init__(url=url, config=config)
        self._reaper = _ProcessReaper.get_instance()

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
        spec = job.spec
        if not spec:
            raise InvalidJobException('Missing specification')

        p = _ChildProcessEntry(job, self, self._get_launcher(self._get_launcher_name(spec)))
        assert p.launcher
        args = p.launcher.get_launch_command(job)

        try:
            with job._status_cv:
                if job.status.state == JobState.CANCELED:
                    raise SubmitException('Job canceled')
            logger.debug('Running %s,  out=%s, err=%s', args, spec.stdout_path, spec.stderr_path)
            p.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         close_fds=True, cwd=spec.directory, env=_get_env(spec))
            self._reaper.register(p)
            job._native_id = p.process.pid
            self._update_job_status(job, JobStatus(JobState.QUEUED, time=time.time(),
                                                   metadata={'nativeId': job._native_id}))
            self._update_job_status(job, JobStatus(JobState.ACTIVE, time=time.time()))
        except Exception as ex:
            raise SubmitException('Failed to submit job', exception=ex)

    def cancel(self, job: Job) -> None:
        """
        Cancels a job.

        :param job: The job to cancel.
        """
        with job._status_cv:
            if job.status.state == JobState.NEW:
                job._set_status(JobStatus(JobState.CANCELED))
                return
        self._reaper.cancel(job)

    def _process_done(self, p: _ProcessEntry) -> None:
        assert p.exit_code is not None
        message = None
        if p.exit_code == 0:
            state = JobState.COMPLETED
        elif p.exit_code < 0 and p.kill_flag:
            state = JobState.CANCELED
        else:
            # We want to capture errors in the launcher scripts. Since, under nomral circumstances,
            # the exit code of the launcher is the exit code of the job, we must use a different
            # mechanism to distinguish between job errors and launcher errors. So we delegate to
            # the launcher implementation to figure out if the error belongs to the job or not
            if p.launcher and p.out and p.launcher.is_launcher_failure(p.out):
                message = p.launcher.get_launcher_failure_message(p.out)
            state = JobState.FAILED

        self._update_job_status(p.job, JobStatus(state, time=p.done_time, exit_code=p.exit_code,
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
        pid = int(native_id)

        self._reaper.register(_AttachedProcessEntry(job, psutil.Process(pid), self))
        # We assume that the native_id above is a PID that was obtained at some point using
        # list(). If so, the process is either still running or has completed. Either way, we must
        # bring it up to ACTIVE state
        self._update_job_status(job, JobStatus(JobState.QUEUED, time=time.time()))
        self._update_job_status(job, JobStatus(JobState.ACTIVE, time=time.time()))

    def _update_job_status(self, job: Job, job_status: JobStatus) -> None:
        job._set_status(job_status, self)
        if self._cb:
            self._cb.job_status_changed(job, job_status)

    def _get_launcher_name(self, spec: JobSpec) -> str:
        if spec.launcher is None:
            return 'single'
        else:
            return spec.launcher


__PSI_J_EXECUTORS__ = [LocalJobExecutor]
