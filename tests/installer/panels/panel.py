from abc import abstractmethod

from textual.containers import Vertical
from textual.widget import Widget

from ..state import State


class Panel(Vertical):
    def __init__(self, state: State) -> None:
        self.state = state
        self._widgets = self._build_widgets()
        Vertical.__init__(self, self._widgets, classes='panel-wrapper')
        self.active = False

    @property
    def widgets(self) -> Widget:
        return self._widgets

    @abstractmethod
    def _build_widgets(self) -> Widget:
        pass

    @property
    @abstractmethod
    def label(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def validate(self) -> bool:
        pass

    async def activate(self) -> None:
        pass
