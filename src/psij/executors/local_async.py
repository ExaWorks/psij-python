"""This module contains the local :class:`~psij.JobExecutor`."""
import asyncio
import logging
import subprocess
import tempfile
from asyncio.subprocess import Process

import time
from abc import ABC
from pathlib import Path
from typing import Optional, Dict, List, cast, Union
from aiofile import async_open

import psutil

from psij import InvalidJobException, SubmitException, ResourceSpecV1
from psij import JobSpec, JobExecutorConfig, JobState, JobStatus
from psij import AsyncJobExecutor
from psij.async_job import AsyncJob
from psij.executors.batch.batch_scheduler_executor import _env_to_mustache
from psij.executors.batch.script_generator import TemplatedScriptGenerator
from psij.executors.local import _format_shell_cmd
from psij.utils import _FileCleaner, _get_async_updater

from psij.executors.batch.template_function_library import ALL as FUNCTION_LIBRARY


logger = logging.getLogger(__name__)


class _ProcessWrapper(ABC):
    def __init__(self, process: Union[Process, psutil.Process]) -> None:
        self.process = process
        self.kill_flag = False

    def kill(self) -> None:
        self.kill_flag = True
        assert self.process is not None
        try:
            root = psutil.Process(self.process.pid)
            for proc in root.children(recursive=True):
                proc.kill()
            self.process.kill()
        except psutil.NoSuchProcess:
            pass


class _ChildProcessWrapper(_ProcessWrapper):
    def __init__(self, process: Process) -> None:
        super().__init__(process)


class _AttachedProcessWrapper(_ProcessWrapper):
    def __init__(self, process: psutil.Process) -> None:
        super().__init__(process)


class AsyncLocalJobExecutor(AsyncJobExecutor):
    """
    An async job executor that runs jobs locally.

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
        self._processes: Dict[str, _ProcessWrapper] = {}
        self._work_dir = Path.home() / '.psij' / 'work' / 'local'
        self._work_dir.mkdir(parents=True, exist_ok=True)
        cast(_FileCleaner, _FileCleaner.get_instance()).clean(self._work_dir)
        self.generator = TemplatedScriptGenerator(config, Path(__file__).parent / 'local'
                                                  / 'local.mustache')

    async def _generate_nodefile(self, job: AsyncJob) -> Optional[str]:
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
            with tempfile.NamedTemporaryFile(suffix='.nodelist', delete=False) as file:
                nodefile = file.name
                async with async_open(file.file) as afile:  # type: ignore
                    for i in range(n):
                        await afile.write('localhost\n'.encode())
            return nodefile
        else:
            raise SubmitException('Cannot handle resource specification with version %s'
                                  % job.spec.resources.version)

    async def submit(self, job: AsyncJob) -> None:
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
        launcher = self._get_launcher(self._get_launcher_name(spec))

        launch_command = launcher.get_launch_command(job)
        updater = await _get_async_updater()

        nodefile = await self._generate_nodefile(job)
        ctx = {
            'job': job,
            'env': _env_to_mustache(job),
            'psij': {
                'lib': FUNCTION_LIBRARY,
                'launch_command': launch_command,
                'script_dir': str(self._work_dir),
                'us_file': updater.update_file_name,
                'us_port': updater.update_port,
                'us_addrs': '127.0.0.1',
                'debug': logger.isEnabledFor(logging.DEBUG),
                'nodefile': nodefile
            }
        }

        submit_file_path = self._work_dir / (job.id + '.job')
        async with async_open(submit_file_path, 'w') as submit_file:
            for chunk in self.generator.render(job, ctx):
                await submit_file.write(chunk)

        await updater.register_job(job, self)
        submit_file_str = str(submit_file_path.absolute())
        try:
            async with job._status_cv:
                if job.status.state == JobState.CANCELED:
                    raise SubmitException('Job canceled')
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('Running %s', _format_shell_cmd(['/bin/bash', submit_file_str]))

            p = await asyncio.create_subprocess_exec('/bin/bash', submit_file_str,
                                                     stdout=subprocess.PIPE,
                                                     stderr=subprocess.STDOUT,
                                                     close_fds=True, cwd=spec.directory)
            pw = _ChildProcessWrapper(p)
            self._processes[job.id] = pw
            job.native_id = str(p.pid)
            await job.set_status(JobStatus(JobState.QUEUED, time=time.time(),
                                           metadata={'nativeId': job._native_id}))
            await job.set_status(JobStatus(JobState.ACTIVE, time=time.time()))
            asyncio.create_task(self._wait_for_child_job(job, pw))
        except Exception as ex:
            updater.unregister_job(job)
            try:
                del self._processes[job.id]
            except KeyError:
                pass
            raise SubmitException('Failed to submit job', exception=ex)

    async def _wait_for_child_job(self, job: AsyncJob, pw: _ChildProcessWrapper) -> None:
        try:
            process = pw.process
            (bout, _) = await process.communicate()
            ec = process.returncode
            assert ec is not None
            await self._process_done(job, pw, bout.decode(), ec)
        except Exception as ex:
            logger.info('Error waiting for child process', exc_info=ex)
            await job.set_status(JobStatus(JobState.FAILED, message=str(ex)))

    async def _wait_for_attached_job(self, job: AsyncJob, pw: _AttachedProcessWrapper) -> None:
        try:
            process = pw.process
            assert isinstance(process, psutil.Process)
            while True:
                if process.is_running():
                    await asyncio.sleep(0.5)
                else:
                    ec = process.wait()
                    if ec is None:
                        ec = 0
                    await self._process_done(job, pw, '', ec)
                    return
        except Exception as ex:
            logger.info('Error waiting for child process', exc_info=ex)
            await job.set_status(JobStatus(JobState.FAILED, message=str(ex)))

    async def _process_done(self, job: AsyncJob, pw: _ProcessWrapper, out: str, ec: int) -> None:
        logger.debug('%s Process done. EC: %s', job.id, ec)
        message = None
        if ec == 0:
            state = JobState.COMPLETED
        elif ec < 0 and pw.kill_flag:
            state = JobState.CANCELED
        else:
            # We want to capture errors in the launcher scripts. Since, under normal circumstances,
            # the exit code of the launcher is the exit code of the job, we must use a different
            # mechanism to distinguish between job errors and launcher errors. So we delegate to
            # the launcher implementation to figure out if the error belongs to the job or not
            if out and '_PSIJ_SCRIPT_DONE' not in out:
                message = out
            state = JobState.FAILED

        if state.final:
            self._clean_submit_file(job)
        # We need to ensure that the status updater has processed all updates that
        # have been sent up to this point
        updater = await _get_async_updater()
        await updater.flush()
        updater.unregister_job(job)
        await job.set_status(JobStatus(state, exit_code=ec, message=message))

    async def cancel(self, job: AsyncJob) -> None:
        """
        Cancels a job.

        :param job: The job to cancel.
        """
        updater = await _get_async_updater()
        updater.unregister_job(job)
        await job.set_status(JobStatus(JobState.CANCELED))
        self._processes[job.id].kill()

    def _clean_submit_file(self, job: AsyncJob) -> None:
        submit_file_path = self._work_dir / (job.id + '.job')
        try:
            submit_file_path.unlink()
        except FileNotFoundError:
            pass

    async def list(self) -> List[str]:
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

    async def attach(self, job: AsyncJob, native_id: str) -> None:
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

        job.native_id = str(pid)

        try:
            process = psutil.Process(pid)
            logger.info('Attached to process %s.', pid)
            updater = await _get_async_updater()
            await updater.register_job(job, self)
            await job.set_status(JobStatus(JobState.QUEUED, time=time.time()))
            await job.set_status(JobStatus(JobState.ACTIVE, time=time.time()))
            asyncio.create_task(self._wait_for_attached_job(job, _AttachedProcessWrapper(process)))
        except psutil.NoSuchProcess:
            raise SubmitException(f'No process with PID {pid} found.')

    def _get_launcher_name(self, spec: JobSpec) -> str:
        if spec.launcher is None:
            return 'single'
        else:
            return spec.launcher
