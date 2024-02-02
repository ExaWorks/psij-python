import urllib
from enum import Enum, Flag
from pathlib import Path
from typing import Optional, Union


class URI:
    def __init__(self, urlstring: str) -> None:
        self.parts = urllib.parse.urlparse(urlstring)

    # a __getattr__ solution may be simpler, but doesn't play well with IDEs and
    # is not quite self-documenting
    @property
    def hostname(self) -> Optional[str]:
        return self.hostname

    @property
    def port(self) -> int:
        return self.port

    @property
    def scheme(self) -> str:
        return self.parts.scheme

    @property
    def netloc(self) -> str:
        return self.parts.netloc

    @property
    def path(self) -> str:
        return self.parts.path

    @property
    def params(self) -> str:
        return self.parts.params

    @property
    def query(self) -> str:
        return self.parts.query

    @property
    def fragment(self) -> str:
        return self.parts.fragment

    @property
    def username(self) -> str:
        return self.parts.username

    @property
    def password(self) -> str:
        return self.parts.password

    def __str__(self) -> str:
        return self.parts.geturl()


class StagingMode(Enum):
    COPY = 1
    LINK = 2
    MOVE = 3


class StageOutFlags(Flag):
    IF_PRESENT = 1
    ON_SUCCESS = 2
    ON_ERROR = 4
    ON_CANCEL = 8
    ALWAYS = ON_SUCCESS | ON_ERROR | ON_CANCEL


class StageIn:
    def __init__(self, source: Union[URI, str], target: Union[str, Path],
                 mode: StagingMode = StagingMode.COPY) -> None:
        if isinstance(source, str):
            source = URI(source)
        if isinstance(target, str):
            target = Path(target)
        self.source = source
        self.target = target
        self.mode = mode

class StageOut:
    def __init__(self, source: Union[str, Path], target: Union[str, URI],
                 flags: StageOutFlags = StageOutFlags.ALWAYS,
                 mode: StagingMode = StagingMode.COPY):
        if isinstance(source, str):
            source = Path(source)
        if isinstance(target, str):
            target = URI(target)

        self.source = source
        self.target = target
        self.flags = flags
        self.mode = mode
