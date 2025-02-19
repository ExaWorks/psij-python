from textual.app import RenderResult
from typing import Optional, Any
from textual.binding import Binding
from textual.events import Blur
from textual.widgets import Select, Button, LoadingIndicator, Input


class MSelect(Select[str]):
    BINDINGS = [
        Binding('enter, space', 'show_overlay2', 'Show menu', show=False),
        Binding('down', 'down', 'Bypass', show=False),
        Binding('up', 'up', 'Bypass', show=False),
    ]

    def action_show_overlay(self) -> None:
        pass

    def action_up(self) -> None:
        self.app.action_scroll_up()  # type: ignore

    def action_down(self) -> None:
        self.app.action_scroll_down()  # type: ignore

    def action_show_overlay2(self) -> None:
        super().action_show_overlay()


class ShortcutButton(Button):
    def __init__(self, label: str, *args: Any, **kwargs: Any) -> None:
        self.key: Optional[str] = None
        label = self._handle_shortcut(label)
        super().__init__(label, *args, **kwargs)

    def on_mount(self) -> None:
        if self.key:
            self.app.register_button_shortcut(self.key, self)  # type: ignore

    def _handle_shortcut(self, label: str) -> str:
        ix = label.index('&')
        if ix == -1:
            return label
        self.key = label[ix + 1]
        return (label[0:ix] + '[b bright_yellow]' + label[ix + 1]
                + '[/b bright_yellow]' + label[ix + 2:])

    def set_label(self, label: str) -> None:
        self.label = self._handle_shortcut(label)


class DottedLoadingIndicator(LoadingIndicator):
    def render(self) -> RenderResult:
        text = super().render()
        text.plain = '......'  # type: ignore
        return text
