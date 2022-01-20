import sys

from psij import JobExecutor, Launcher


def _print_status() -> None:
    print('*** Plugin status ***')
    JobExecutor._print_plugin_status()
    Launcher._print_plugin_status()


if sys.argv[1] == 'plugins':
    _print_status()
