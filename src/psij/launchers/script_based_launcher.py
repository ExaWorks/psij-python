from pathlib import Path
from typing import Optional, List

from psij.launchers.launcher import Launcher
from psij.job_executor_config import JobExecutorConfig
from psij.job import Job


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
    the :func:`~psij.launchers.script_based_launcher.ScriptBasedLauncher._get_additional_args`
    function.

    The remaining arguments to the script are the job executable and arguments.

    A simple script library is provided in scripts/lib.sh. Its use is optional and it is intended
    to be included in a main launcher script using a standard C preprocessor. It does the following:

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
    """

    def __init__(self, script_path: Path, config: Optional[JobExecutorConfig] = None) -> None:
        """
        Initializes this launcher.

        :param script_path: A path to a script that is invoked as described above.
        :param config: An optional configuration.
        """
        super().__init__(config)
        self._script_path = script_path
        self._log_file = ''
        if config and config.launcher_log_file:
            self._log_file = str(config.launcher_log_file)

    def get_launch_command(self, job: Job) -> List[str]:
        """See :func:`~psij.launchers.launcher.Launcher.get_launch_command`."""
        spec = job.spec
        assert spec is not None

        args = ['/bin/bash', str(self._script_path), job.id, _str(self._log_file),
                _str(spec.pre_launch), _str(spec.post_launch), _path(spec.stdin_path),
                _path(spec.stdout_path), _path(spec.stderr_path)]
        args += self._get_additional_args(job)
        assert spec.executable is not None
        args += [spec.executable]
        if spec.arguments is not None:
            args += spec.arguments

        return args

    def _get_additional_args(self, job: Job) -> List[str]:
        """
        Returns any additional arguments, after first mandatory four, to be passed to the script.

        :param job: The job that is being launched.
        """
        return []

    def is_launcher_failure(self, output: str) -> bool:
        """See :func:`~psij.launchers.launcher.Launcher.is_launcher_failure`."""
        return output.split('\n')[-1] != '_PSI_J_LAUNCHER_DONE'

    def get_launcher_failure_message(self, output: str) -> str:
        """See :func:`~psij.launchers.launcher.Launcher.get_launcher_failure_message`."""
        return '\n'.join(output.split('\n')[:-1])
