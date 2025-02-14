import os
import subprocess
import time
from abc import ABC, abstractmethod
import random
from tempfile import mkstemp
from typing import Optional, Tuple

from installer.log import log


def _run(cmd: str, input: Optional[str] = None) -> Tuple[int, str]:
    p = subprocess.run(['/bin/bash', '-c', cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       input=input, text=True)
    return p.returncode, p.stdout


def _must_succeed(cmd: str, input: Optional[str] = None) -> str:
    ec, out = _run(cmd, input)
    if ec != 0:
        raise Exception(f'Command {cmd} failed: {out}')
    return out


def _succeeds(cmd: str, input: Optional[str] = None) -> bool:
    ec, _ = _run(cmd, input)
    return ec == 0


def _save_env() -> None:
    _must_succeed('declare -x | egrep -v "^declare -x '
                  '(BASH_VERSINFO|DISPLAY|EUID|GROUPS|SHELLOPTS|TERM|UID|_)=" >psij-ci-env')


class InstallMethod(ABC):
    @abstractmethod
    def is_available(self) -> Tuple[bool, Optional[str]]:
        pass

    @abstractmethod
    def install(self) -> None:
        pass

    @abstractmethod
    def already_installed(self) -> bool:
        pass

    @property
    @abstractmethod
    def preview(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def label(self) -> str:
        pass

    @property
    @abstractmethod
    def help_message(self) -> str:
        pass


class Crontab(InstallMethod):
    def __init__(self) -> None:
        cwd = os.getcwd()
        hour = random.randint(0, 23)
        minute = random.randint(0, 59)
        self.line = f'{minute} {hour} * * * "{cwd}/psij-ci-run" --log'

    def is_available(self) -> Tuple[bool, Optional[str]]:
        if not _succeeds("ps -eo command | awk '{print $1}' | grep cron"):
            return False, 'not found'
        if _succeeds('crontab -l 2>&1 | grep "not allowed"'):
            return False, 'not allowed'
        return True, None

    def _crt_crontab(self) -> str:
        ec, out = _run('crontab -l')
        if ec != 0:
            if 'no crontab for' in out:
                return ''
            else:
                raise Exception(f'Error getting crontab: {out}')
        else:
            return out

    def already_installed(self) -> bool:
        cwd = os.getcwd()
        out = self._crt_crontab()
        if f'cd "{cwd}" && ./psij-ci-run' in out or '"{cwd}/psij-ci-run"' in out:
            return True
        else:
            return False

    def install(self) -> None:
        crt = self._crt_crontab()
        _save_env()
        _must_succeed('crontab -', input=f'{crt}\n{self.line}\n')

    @property
    def preview(self) -> str:
        return self.line

    @property
    def name(self) -> str:
        return 'cron'

    @property
    def label(self) -> str:
        return 'Cron - the standard UNIX job scheduler'

    @property
    def help_message(self) -> str:
        return 'Uses the Cron scheduler to schedule daily runs of the tests.'


class At(InstallMethod):
    def __init__(self) -> None:
        self.hour = random.randint(0, 23)
        self.minute = random.randint(0, 59)
        self.cmd = f'psij-ci-run --reschedule {self.hour}:{self.minute} --log'

    def is_available(self) -> Tuple[bool, Optional[str]]:
        fd, path = mkstemp()
        os.close(fd)

        try:
            ec, out = _run('at now', input=f'rm {path}')
            if ec != 0:
                return False, 'not found'
            time.sleep(0.2)
            if out.startswith('job'):
                job_no = out.split()[1]
                _run(f'atrm {job_no}')
                if 'No atd' in out:
                    return False, 'not running'
            if os.path.exists(path):
                os.remove(path)
                return False, 'unknown error'
            return True, None
        finally:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def already_installed(self) -> bool:
        out = _must_succeed('atq')
        out = out.strip()
        if len(out) == 0:
            return False
        for line in out.split('\n'):
            job_no = line.split()[0]
            job = _must_succeed(f'at -c {job_no}')
            if 'psij-ci-run' in job:
                return False
        return True

    def install(self) -> None:
        _must_succeed(f'at {self.hour}:{self.minute}', input=self.cmd)

    @property
    def preview(self) -> str:
        return f'echo "{self.cmd}" | at {self.hour}:{self.minute}'

    @property
    def name(self) -> str:
        return 'at'

    @property
    def label(self) -> str:
        return 'at - the standard UNIX "at" command'

    @property
    def help_message(self) -> str:
        return ('Uses the "at" job scheduler to schedule the tests which then re-schedule '
                'themselves.')


class Screen(InstallMethod):
    def __init__(self) -> None:
        self.cmd = 'screen -d -m bash -c "./psij-ci-run --repeat --log"'

    def is_available(self) -> Tuple[bool, Optional[str]]:
        if _succeeds('which screen'):
            return True, None
        else:
            return False, 'not found'

    def already_installed(self) -> bool:
        ec, out = _run('screen -list | grep psij-ci-run')
        return ec == 0

    def install(self) -> None:
        _must_succeed(self.cmd)

    @property
    def preview(self) -> str:
        return self.cmd

    @property
    def name(self) -> str:
        return 'screen'

    @property
    def label(self) -> str:
        return 'Screen - the Screen terminal multiplexer'

    @property
    def help_message(self) -> str:
        return ('Uses GNU Screen to run the tests in a Screen session. Does not persist across '
                'reboots.')


class Custom(InstallMethod):
    def is_available(self) -> Tuple[bool, Optional[str]]:
        return True, None

    def already_installed(self) -> bool:
        return False

    def install(self) -> None:
        _save_env()

    @property
    def preview(self) -> str:
        cwd = os.getcwd()
        return f'"{cwd}/psij-ci-run" --log'

    @property
    def name(self) -> str:
        return 'custom'

    @property
    def label(self) -> str:
        return 'Custom - run with custom tool'

    @property
    def help_message(self) -> str:
        return ('Prints a command that can be used to run the tests, which can then be used with '
                'a custom scheduler.')


METHODS = [
    Crontab(),
    At(),
    Screen(),
    Custom()
]


def existing() -> Optional[InstallMethod]:
    for method in METHODS:
        if method.already_installed():
            return method
        else:
            log.write(f'Not installed {method.name}\n')
    return None
