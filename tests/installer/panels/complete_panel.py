from .panel import Panel
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Label


class CompletePanel(Panel):
    def _build_widgets(self) -> Widget:
        return Vertical(
            Label('Installation complete.',
                  classes='header', shrink=True, expand=True),
            Label('The PSI/J CI tests have been installed. You can press the Exit button below '
                  'to exit this installer.',
                  classes='main-text', shrink=True, expand=True),
            classes='panel'
        )

    @property
    def label(self) -> str:
        return 'Complete'

    @property
    def name(self) -> str:
        return 'complete'

    async def validate(self) -> bool:
        return True

    async def activate(self) -> None:
        pass
