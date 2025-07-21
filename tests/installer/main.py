from .terminal import run_patches, terminal_supports_unicode
run_patches()

import asyncio
import types

from .dialogs import ExitConfirmDialog
from .state import State
from .log import log
from .panels.basic_info_panel import BasicInfoPanel
from .panels.batch_scheduler_panel import BatchSchedulerPanel
from .panels.intro_panel import IntroPanel
from .panels.key_panel import KeyPanel
from .panels.schedule_panel import SchedulePanel
from .panels.complete_panel import CompletePanel
from .widgets import ShortcutButton

from textual import on, events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static, Label, Button
from typing import Optional, Dict, cast, List


class PSIJCIInstallWizard(App[object]):
    CSS_PATH = 'style.tcss'

    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        ('down', 'scroll_down'),
        ('up', 'scroll_up'),
        ('pageup', 'prev_page'),
        ('pagedown', 'next_page'),
        ('ctrl+q', 'confirm_quit', 'Quit'),
        ('ctrl+c', 'quit', 'Quit'),
        ('x', 'confirm_quit'),
        ('alt+x', 'confirm_quit'),
        ('ctrl+x', 'confirm_quit'),
        ('escape', 'confirm_quit')
    ]

    def __init__(self, conftest: types.ModuleType, ci_runner: types.ModuleType) -> None:
        super().__init__()
        self.state = State(conftest, ci_runner)
        self.body = None
        self.shortcuts: Dict[str, List[ShortcutButton]] = {}
        self.key_panel = KeyPanel(self.state)
        self.scheduler_panel = BatchSchedulerPanel(self.state)
        self.install_panel = SchedulePanel(self.state)

        self.panels = [
            IntroPanel(self.state),
            BasicInfoPanel(self.state),
            self.key_panel,
            self.scheduler_panel,
            self.install_panel,
            CompletePanel(self.state)
        ]

    def disable_install(self) -> None:
        self.state.disable_install = True
        self.install_panel.disabled = True
        self.get_widget_by_id('panel-label-install').disabled = True

    def compose(self) -> ComposeResult:
        self.prev_button = ShortcutButton('&Previous', disabled=True, id='btn-prev')
        self.next_button = ShortcutButton('&Next', variant='primary', id='btn-next')

        yield Header(icon='=')
        with Horizontal(id='root'):
            with Vertical(id='sidebar', classes='sidebar') as sidebar:
                self.sidebar = sidebar
                for panel in self.panels:
                    yield Label('  ' + panel.label, id=f'panel-label-{panel.name}',
                                classes='panel-label')
            with Vertical(id='main'):
                with Vertical(id='body', classes='v-scrollable'):
                    for panel in self.panels:
                        yield panel
                with Horizontal(id='bottom'):
                    yield Static('', id='left-padding')
                    with Horizontal(id='buttons'):
                        yield self.prev_button
                        yield self.next_button
                    yield Static('', id='right-padding')
        yield Footer()

    async def on_mount(self) -> None:
        for panel in self.panels:
            panel.widgets.disabled = True
        if self.size.height < 35:
            self.add_class('small')
        else:
            self.add_class('large')
        if not terminal_supports_unicode():
            self.add_class('no-unicode')
        self.set_default_executor()

        body = self.get_widget_by_id('body')

        self.watch(body, 'scroll_y', self._on_y_scroll)
        self.next_button.focus()
        self.activate_panel(0)

    async def _on_y_scroll(self, y: int) -> None:
        log.write(f'on_y_scroll({y})\n')
        cy = y + self.size.height / 2
        for i in range(len(self.panels)):
            # parent because all panels are wrapped
            panel = self.panels[i]
            region = panel.widgets.virtual_region
            if cy >= region.y and cy <= region.bottom:
                self.activate_panel(i, False)
                break

    def done(self) -> None:
        super().exit()

    def activate_panel(self, n: int, scroll: Optional[bool] = True) -> None:
        if n == len(self.panels):
            self.done()
        asyncio.create_task(self.a_activate_panel(n, scroll))

    async def a_activate_panel(self, n: int, scroll: Optional[bool] = True) -> None:
        try:
            if n == self.state.active_panel:
                return
            new_panel = self.panels[n]
            log.write(f'activate_panel({n}: {new_panel}, scroll={scroll})\n')
            labels = cast(List[Label], self.sidebar.children)
            if self.state.active_panel is not None:
                old_panel = self.panels[self.state.active_panel]
                if scroll and n > self.state.active_panel:
                    if not await old_panel.validate():
                        return
                label = labels[self.state.active_panel]
                label.update('  ' + old_panel.label)
                old_panel.widgets.disabled = True
                old_panel.active = False
            for i in range(n):
                labels[i].styles.text_style = 'bold'
            for i in range(n, len(labels)):
                labels[i].styles.text_style = 'none'
            label = labels[n]
            label.update('> ' + new_panel.label)
            self.prev_button.disabled = n == 0
            self.set_next_button(n == len(self.panels) - 1)
            if scroll:
                new_panel.anchor()

            self.state.active_panel = n
            new_panel.active = True
            await new_panel.activate()
            new_panel.widgets.disabled = False
        except Exception as ex:
            import traceback
            log.write(f'Ex: {ex}\n')
            traceback.print_exc(file=log)

    def set_next_button(self, exit: bool) -> None:
        btn_next = self.get_widget_by_id('btn-next')
        assert isinstance(btn_next, ShortcutButton)
        if exit:
            btn_next.set_label('E&xit')
        else:
            btn_next.set_label('&Next')

    def register_button_shortcut(self, char: str, btn: ShortcutButton) -> None:
        char = char.lower()
        if char not in self.shortcuts:
            self.shortcuts[char] = []
        self.shortcuts[char].append(btn)
        self.bind(f'{char}, alt+{char}', 'on_key', show=False)

    def on_key(self, event: events.Key) -> None:
        k = event.key
        if k.startswith('alt+'):
            k = k[4:]
        if k in self.shortcuts:
            btns = self.shortcuts[k]
            for btn in btns:
                if not btn.disabled and btn.is_on_screen:
                    btn.press()

    def action_next_page(self) -> None:
        self.next_button.press()

    def action_prev_page(self) -> None:
        self.prev_button.press()

    def action_scroll_down(self) -> None:
        body = self.get_widget_by_id('body')
        body.scroll_down()

    def action_scroll_up(self) -> None:
        body = self.get_widget_by_id('body')
        body.scroll_up()

    @on(Button.Pressed, '#btn-next')
    async def next_item(self) -> None:
        try:
            assert self.state.active_panel is not None
            self.activate_panel(self.next_enabled_panel(self.state.active_panel, 1))
        except IndexError:
            log.write('No next panel. Exiting\n')
            await self.action_quit()

    def next_enabled_panel(self, crt: int, delta: int) -> int:
        crt += delta
        while crt < len(self.panels) and crt >= 0:
            if self.panels[crt].disabled:
                crt += delta
            else:
                return crt
        raise IndexError('No next enabled panel')

    @on(Button.Pressed, '#btn-prev')
    async def prev_item(self) -> None:
        assert self.state.active_panel is not None
        self.activate_panel(self.next_enabled_panel(self.state.active_panel, -1))

    def _focus_next(self) -> None:
        btn = self.get_widget_by_id('btn-next')
        btn.focus()

    def action_confirm_quit(self) -> None:
        asyncio.create_task(self._confirm_quit())

    async def _confirm_quit(self) -> None:
        result = await ExitConfirmDialog().run(self)
        if result == 'cancel':
            return
        await self.action_quit()

    async def action_quit(self) -> None:
        install_method = self.state.install_method
        messages = []
        if self.state.conf_backed_up:
            messages.append('Your previous configuration was saved in "testing.conf.bk"')
        if install_method is not None and install_method.name == 'custom':
            messages.append(f'Tests can be run with the following command:\n'
                            f'\t{install_method.preview}')
        if len(messages) > 0:
            self.exit(message='\n\n'.join(messages))
        else:
            self.exit()

    def set_default_executor(self) -> None:
        label, name = self.state.get_batch_executor()
        if name is None:
            name = 'none'

        batch_warner = self.get_widget_by_id('warn-no-batch')
        if name == 'none':
            batch_warner.remove_class('hidden')
        else:
            batch_warner.add_class('hidden')

        self.scheduler_panel.set_scheduler(name)


def run(conftest: types.ModuleType, ci_runner: types.ModuleType) -> None:
    PSIJCIInstallWizard(conftest, ci_runner).run()
