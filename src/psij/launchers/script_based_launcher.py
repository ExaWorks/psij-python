import hashlib
import logging
import secrets
import threading
from pathlib import Path
from typing import Optional, List, Any

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


_BLOCK_SZ = 16384


def _copy_and_checksum(src_path: Path, dst_path: Path, s: Any) -> None:
    with open(src_path, 'rb') as src:
        with open(dst_path, 'wb') as dst:
            bytes = src.read(_BLOCK_SZ)
            dst.write(bytes)
            s.update(bytes)
    dst_path.chmod(src_path.stat().st_mode)


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
    * redirects stdout and stderr to the log file, while prepending a timestamp and the
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

            deploy_dir = self._deploy_files(self._files_to_deploy())
            self._deployed_script_path = deploy_dir / self._script_path.name
            self._deployed = True

    def _files_to_deploy(self) -> List[Path]:
        return [
            Path(__file__).parent / 'scripts' / 'launcher_lib.sh',
            self._script_path
        ]

    def _deploy_files(self, paths: List[Path]) -> Path:
        """
        Deploys all files in a list to the same subdirectory of `config.work_directory`.

        The directory is guaranteed to be unique for each distinct list of files. That is,
        two invocations of this method with byte-by-byte identical files pointed to by `paths`
        and in the same order, will lead to the same subdirectory; changing the order of files
        in `paths` or changing the contents of one or more files in the list will lead to
        a different subdirectory.
        This allows files deployed together through this method to maintain relative references
        to each other while ensuring that different processes using different files do not interfere
        with each other.
        """
        wrk_dir = self.config.work_directory
        wrk_dir.mkdir(parents=True, exist_ok=True)

        tmp_prefix = secrets.token_hex() + '_'
        h = hashlib.sha256()
        tmp_paths = {}
        for path in paths:
            tmp_path = wrk_dir / (tmp_prefix + path.name)
            tmp_paths[path] = tmp_path
            _copy_and_checksum(path, tmp_path, h)

        dst_dir = wrk_dir / h.hexdigest()

        if dst_dir.exists():
            for path in paths:
                tmp_paths[path].unlink()
            return dst_dir
        dst_dir.mkdir(exist_ok=True)

        for path in paths:
            dst_path = dst_dir / path.name
            try:
                # this appears to use os.rename, although I'd wish pathlib docs would state this
                # explicitly, since the docs for Path.rename mention nothing of the exceptions
                # thrown

                tmp_paths[path].rename(dst_path)
            except FileExistsError:
                # thrown in Windows if the path already exists, which is fine if the destination is
                # a file; we were racing another process
                if dst_path.is_dir():
                    raise
                else:
                    continue
            except IsADirectoryError:
                # this is thrown in Unix if the destination exists and is a directory; we're not
                # expecting this
                raise
        return dst_dir

    def get_launch_command(self, job: Job, log_file: Optional[str] = None) -> List[str]:
        """See :func:`~psij.Launcher.get_launch_command`."""
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
        """See :func:`~psij.Launcher.is_launcher_failure`."""
        return output.split('\n')[-2] != '_PSI_J_LAUNCHER_DONE'

    def get_launcher_failure_message(self, output: str) -> str:
        """See :func:`~psij.Launcher.get_launcher_failure_message`."""
        # If, according to the above, it is a launcher failure, then
        # the magic line should not be present (aka, all of the output
        # is the failure).
        return output
