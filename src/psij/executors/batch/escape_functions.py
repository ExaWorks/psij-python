import pathlib
import shlex


def bash_escape(o: object) -> str:
    """Escape object to bash string.

    Renders and escapes an object to a string such that its value is preserved when substituted
    in a bash script between double quotes. Numeric values are simply rendered without any
    escaping. Path objects are converted to absolute path and escaped. All other objects are
    converted to string and escaped.

    Parameters
    ----------
    o
        The object to escape.

    Returns
    -------
    An escaped representation of the object that can be substituted in bash scripts.
    """
    if isinstance(o, int):
        return str(o)
    if isinstance(o, float):
        return str(o)
    if isinstance(o, pathlib.Path):
        o = o.absolute()
    s = str(o)
    return shlex.quote(s)
