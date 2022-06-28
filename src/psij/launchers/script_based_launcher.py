import atexit
import logging
import secrets
import shutil
import tempfile
import threading
from datetime import timedelta

import time
from pathlib import Path
from typing import Dict, Optional, List, Type

from psij.job_launcher import Launcher
from psij.job_executor_config import JobExecutorConfig
from psij.job import Job


logger = logging.getLogger(__name__)


def _str(obj: Optional[object]) -> str:
    if obj is not None:
        return str(obj)
    else:
        return ''


def _path(obj: Optional[object]) -> str:
    if obj is None:
        return '/dev/null'
    else:
        return str(obj)


_SANDBOX_PREFIX = 'sbx-'
_SANDBOX_CLEAN_TIME = timedelta(days=2).total_seconds()


class _ProcessSandbox:
    _instances = {}  # type: Dict[Path, _ProcessSandbox]
    _instances_lock = threading.RLock()
    _mark_initialized = False

    def __init__(self, config: JobExecutorConfig) -> None:
        self.config = config
        self.lock = threading.RLock()
        self.created = False
        self.dir = None  # type: Optional[Path]

    def get_dir(self) -> Path:
        with self.lock:
            if not self.created:
                self.create()
            assert self.dir is not None
            return self.dir

    def create(self) -> None:
        self.config.work_directory.mkdir(parents=True, exist_ok=True)
        self.dir = Path(tempfile.mkdtemp(prefix=_SANDBOX_PREFIX, dir=self.config.work_directory))
        self.created = True

    def mark_unused(self) -> None:
        try:
            assert self.dir is not None
            with open(self.dir / '.stale', 'w'):
                pass
        except Exception:
            pass

    def clean(self) -> None:
        now = time.time()
        if not self.config.work_directory.exists():
            return
        for child in self.config.work_directory.iterdir():
            if child.name.startswith(_SANDBOX_PREFIX):
                marker = child / '.stale'
                if marker.exists() and now - marker.stat().st_mtime > _SANDBOX_CLEAN_TIME:
                    shutil.rmtree(child, ignore_errors=True)

    @classmethod
    def get_sandbox(cls: Type['_ProcessSandbox'], config: JobExecutorConfig) -> '_ProcessSandbox':
        with _ProcessSandbox._instances_lock:
            if not _ProcessSandbox._mark_initialized:
                atexit.register(_ProcessSandbox.mark_all)
                _ProcessSandbox._mark_initialized = True

            if config.work_directory not in _ProcessSandbox._instances:
                inst = _ProcessSandbox(config)
                _ProcessSandbox._instances[config.work_directory] = inst

                threading.Thread(target=inst.clean).start()
            return _ProcessSandbox._instances[config.work_directory]

    @classmethod
    def mark_all(cls: Type['_ProcessSandbox']) -> None:
        for sandbox in _ProcessSandbox._instances.values():
            sandbox.mark_unused()


class ScriptBasedLauncher(Launcher):
    """
    A launcher that uses a script to start the job, possibly by wrapping it in other tools.

    This launcher is an abstract base class for launchers that wrap the job in a script. The script
    must be a bash script and is invoked with the first four parameters as:

    * the job ID
    * a launcher log file, which is taken from the launcher_log_file configuration setting and
      defaults to `/dev/null`
    * the pre- and post- launcher scripts, or empty strings if they are not specified

    Additional positional arguments to the script can be specified by subclasses by overriding
    the :meth:`~.get_additional_args` method.

    The remaining arguments to the script are the job executable and arguments.

    A simple script library is provided in scripts/launcher_lib.sh. Its use is optional and it is
    intended to be included at the beginning of a main launcher script using
    `source $(dirname "$0")/launcher_lib.sh`. It does the following:

    * sets '-e' mode (exit on error)
    * sets the variables _PSI_J_JOB_ID, _PSI_J_LOG_FILE, _PSI_J_PRE_LAUNCH, and
      _PSI_J_POST_LAUNCH from the first arguments, as specified above.
    * saves the current stdout and stderr in descriptors 3 and 4, respectively
    * redirects stdout and stderr to the log file, while pre-pending a timestamp and the
      job ID to each line
    * defines the commands "pre_launch" and "post_launch", which can be invoked by the main
      script.

    When invoking the job executable (either directly or through a launch command), it is
    recommended that the stdout and stderr of the job process be redirected to descriptors 3 and 4,
    respectively, such that they can be captured by the entity invoking the launcher rather than
    ending up in a the launcher log file.

    A successful completion of the launcher should be signalled by the launcher by printing the
    string "_PSI_J_LAUNCHER_DONE" to stdout. The launcher can then exit with the exit code returned
    by the launched command. This allows executor to distinguish between a non-zero exit code due to
    application failure or due to a premature launcher failure.

    The actual launcher scripts, as well as the library, are deployed at run-time into the work
    directory, where submit scripts are also generated. This directory is meant to be accessible
    by both the node submitting the job as well as the node launching the job.
    """

    def __init__(self, script_path: Path, config: Optional[JobExecutorConfig] = None) -> None:
        """
        Initializes this launcher.

        Parameters
        ----------
        script_path
            A path to a script that is invoked as described above.
        config
            An optional configuration.
        """
        super().__init__(config)
        self._script_path = script_path
        self._log_file = ''
        if config and config.launcher_log_file:
            self._log_file = str(config.launcher_log_file)
        self._lock = threading.RLock()
        self._deployed = False

    def _ensure_launcher_deployed(self) -> None:
        with self._lock:
            if self._deployed:
                return

            self._deploy_file(Path(__file__).parent / 'scripts' / 'launcher_lib.sh')
            self._deployed_script_path = self._deploy_file(self._script_path)

    def _deploy_file(self, path: Path) -> Path:
        dst_dir = _ProcessSandbox.get_sandbox(self.config).get_dir()
        dst_path = dst_dir / path.name
        if dst_path.exists():
            return dst_path
        tmp_prefix = secrets.token_hex() + '_'
        tmp_path = dst_dir / (tmp_prefix + path.name)
        shutil.copy(path, tmp_path)
        try:
            # this appears to use os.rename, although I'd wish pathlib docs would state this
            # explicitly, since the docs for Path.rename mention nothing of the exceptions thrown
            tmp_path.rename(dst_path)
            return dst_path
        except FileExistsError:
            # thrown in Windows if the path already exists, which is fine if the destination is a
            # file; we were racing another process
            if dst_path.is_dir():
                raise
            else:
                return dst_path
        except IsADirectoryError:
            # this is throw in Unix if the destination exists and is a directory; we're not
            # expecting this
            raise

    def get_launch_command(self, job: Job, log_file: Optional[str] = None) -> List[str]:
        """See :func:`~psij.job_launcher.Launcher.get_launch_command`."""
        spec = job.spec
        assert spec is not None

        self._ensure_launcher_deployed()

        if log_file is None:
            log_file = self._log_file

        args = ['/bin/bash', str(self._deployed_script_path), job.id, _str(log_file),
                _str(spec.pre_launch), _str(spec.post_launch), _path(spec.stdin_path),
                _path(spec.stdout_path), _path(spec.stderr_path)]
        args += self.get_additional_args(job)
        assert spec.executable is not None
        args += [spec.executable]
        if spec.arguments is not None:
            args += spec.arguments

        return args

    def get_additional_args(self, job: Job) -> List[str]:
        """
        Returns any additional arguments, after first mandatory four, to be passed to the script.

        :param job: The job that is being launched.
        """
        return []

    def is_launcher_failure(self, output: str) -> bool:
        """See :func:`~psij.job_launcher.Launcher.is_launcher_failure`."""
        return output.split('\n')[-1] != '_PSI_J_LAUNCHER_DONE'

    def get_launcher_failure_message(self, output: str) -> str:
        """See :func:`~psij.job_launcher.Launcher.get_launcher_failure_message`."""
        return '\n'.join(output.split('\n')[:-1])
