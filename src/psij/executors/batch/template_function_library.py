from datetime import timedelta
from typing import Dict, Callable, Any, Union


def walltime_to_minutes(walltime: Union[timedelta, int, str]) -> int:
    """Converts a walltime object to a number of minutes.

    The walltime can either be a Python :class:`~datetime.timedelta`, an integer, in which case
    it is interpreted directly as a number of minutes, or a string with a format of either
    `HH:MM:SS`, `HH:MM`, or `MM`.

    Parameters
    ----------
    walltime
        the walltime to convert
    Returns
    -------
    The number of minutes represented by the `walltime` parameter.
    """
    if isinstance(walltime, timedelta):
        return int(walltime.total_seconds() / 60)
    if isinstance(walltime, int):
        return walltime
    if isinstance(walltime, str):
        return _parse_str_walltime(walltime)
    raise ValueError('Invalid walltime: %s of type %s' % (walltime, type(walltime)))


def _parse_str_walltime(walltime: str) -> int:
    # accept HH:MM:SS or HH:MM or MM
    els = walltime.split(':')
    if len(els) > 3 or len(els) == 0:
        raise ValueError('Invalid walltime format (%s). Expected HH:MM:SS or HH:MM or MM.' %
                         walltime)
    if len(els) == 3:
        try:
            return int(els[0]) * 60 + int(els[1])
        except ValueError as ve:
            raise ValueError('Error parsing walltime (%s) as HH:MM:SS: %s' %
                             (walltime, ve))
    if len(els) == 2:
        try:
            return int(els[0]) * 60 + int(els[1])
        except ValueError as ve:
            raise ValueError('Error parsing walltime (%s) as HH:MM: %s' %
                             (walltime, ve))
    if len(els) == 1:
        try:
            return int(els[0])
        except ValueError as ve:
            raise ValueError('Error parsing walltime (%s) as MM: %s' %
                             (walltime, ve))
    # this is unreachable code, but mypy can't tell
    assert False


ALL: Dict[str, Callable[..., Any]] = {
    'walltime_to_minutes': walltime_to_minutes
}
"""A dictionary of all template-accessible functions for the batch executor templating mechanism.

The dictionary which maps function names to their implementation. All public functions in this
module are present in this dictionary and their corresponding keys are the same as their names.
"""
