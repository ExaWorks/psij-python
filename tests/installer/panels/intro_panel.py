from .panel import Panel
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Label

from ..dialogs import ExistingInstallConfirmDialog
from ..log import log
from ..install_methods import existing


class IntroPanel(Panel):
    def _build_widgets(self) -> Widget:
        return Vertical(
            Label('This tool will guide you in setting up the PSI/J nightly tests.',
                  classes='header', shrink=True, expand=True),
            Label('Hint: you can likely use your terminal\'s application mode (typically the'
                  ' Shift or Option keys) to copy and paste text. For example, Shift+Drag to'
                  ' select text or Shift+Ctrl+V to paste from the clipboard.',
                  classes='help-text', shrink=True, expand=True),
            classes='panel'
        )

    @property
    def label(self) -> str:
        return 'Introduction'

    @property
    def name(self) -> str:
        return 'intro'

    async def validate(self) -> bool:
        return True

    async def activate(self) -> None:
        log.write('Intro activate\n')
        if self.state.disable_install:
            return
        m = existing()
        if m is not None:
            result = await ExistingInstallConfirmDialog(m.name).run(self.app)
            if result == 'quit':
                self.app.exit()
            if result == 'update':
                self.app.disable_install()  # type: ignore
