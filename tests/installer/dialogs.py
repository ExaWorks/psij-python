import asyncio
from typing import cast

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Label, RichLog, ProgressBar

from installer.widgets import DottedLoadingIndicator, ShortcutButton


class RunnableDialog[T](ModalScreen[None]):
    def __init__(self) -> None:
        super().__init__()
        self.done = asyncio.get_running_loop().create_future()

    def set_result(self, result: T) -> None:
        self.done.set_result(result)

    async def wait(self) -> bool:
        return cast(bool, await self.done)

    async def run(self, app: App[object]) -> T:
        app.push_screen(self)
        try:
            await self.done
            return cast(T, self.done.result())
        finally:
            app.pop_screen()


class HelpDialog(RunnableDialog[None]):
    BINDINGS = [
        ('escape', 'close', 'Close'),
        ('c', 'close', 'Close'),
        ('alt+c', 'close', 'Close')
    ]

    def __init__(self, title: str, widget: Widget) -> None:
        super().__init__()
        self.title = title
        self.widget = widget

    def compose(self) -> ComposeResult:
        assert self.title is not None
        yield Vertical(
            Label(self.title, classes='header'),
            Vertical(self.widget, classes='v-scrollable'),
            Horizontal(
                ShortcutButton('&Close', variant='error', id='btn-close'),
                classes='action-area'
            ),
            id='help-dialog', classes='dialog help-dialog'
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.action_close()

    def action_close(self) -> None:
        self.set_result(None)


class ExitConfirmDialog(RunnableDialog[str]):
    BINDINGS = [
        ('escape', 'close'),
        ('c', 'close', 'Close'),
        ('alt+c', 'close', 'Close')
    ]

    def __init__(self) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        self.btn_quit = ShortcutButton('&Quit', variant='error', id='btn-quit')
        self.btn_cancel = ShortcutButton('&Cancel', variant='warning', id='btn-cancel')
        yield Vertical(
            Label('Confirm exit', classes='header'),
            Label('Are you sure you want to exit the installer?',
                  classes='main-text',
                  shrink=True, expand=True),
            Horizontal(self.btn_quit, self.btn_cancel, classes='action-area'),
            id='replace-dialog', classes='dialog error-dialog'
        )

    def action_close(self) -> None:
        self.set_result('cancel')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button == self.btn_quit:
            self.set_result('quit')
        else:
            self.set_result('cancel')


class ProgressDialog(ModalScreen[None]):
    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(self.message, classes='header', shrink=True, expand=True),
            ProgressBar(id='progress-indicator-indeterminate',
                        show_percentage=False, show_bar=True, show_eta=False),
            id='progress-dialog', classes='dialog'
        )


class TestJobsDialog(RunnableDialog[bool]):
    BINDINGS = [
        ('b', 'back', 'Back'),
        ('alt+b', 'back', 'Back'),
        ('c', 'continue', 'Continue'),
        ('alt+c', 'continue', 'Continue'),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.result = None

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label('Running test jobs', classes='header', shrink=True, expand=True),
            Horizontal(
                Label('Single node job', id='label-job-1', classes='test-job-label'),
                Label('[ ', classes='test-job-marker'),
                DottedLoadingIndicator(id='indicator-job-1', classes='test-job-indicator hidden'),
                Label('', id='status-job-1', classes='test-job-status'),
                Label(' ]', classes='test-job-marker'),
                classes='job-progress-row'
            ),
            Horizontal(
                Label('Multi node job ', id='label-job-2', classes='test-job-label'),
                Label('[ ', classes='test-job-marker'),
                DottedLoadingIndicator(id='indicator-job-2', classes='test-job-indicator hidden'),
                Label('', id='status-job-2', classes='test-job-status'),
                Label(' ]', classes='test-job-marker'),
                classes='job-progress-row'
            ),
            RichLog(id='test-job-errors', wrap=True),
            Horizontal(
                ShortcutButton('Go &back', variant='error', id='btn-back'),
                ShortcutButton('&Continue', id='btn-continue'),
                classes='action-area'
            ),
            id='test-jobs-dialog', classes='dialog'
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'btn-back':
            self.action_back()
        else:
            self.action_continue()

    def action_back(self) -> None:
        self.app.pop_screen()
        self.set_result(False)

    def action_continue(self) -> None:
        self.app.pop_screen()
        self.set_result(True)

    def set_running(self, job_no: int) -> None:
        indicator = self.get_widget_by_id(f'indicator-job-{job_no}')
        indicator.remove_class('hidden')

        label = self.get_widget_by_id(f'status-job-{job_no}')
        label.add_class('hidden')

    def set_status(self, job_no: int, status: str, cls: str) -> None:
        indicator = self.get_widget_by_id(f'indicator-job-{job_no}')
        indicator.add_class('hidden')

        label = self.get_widget_by_id(f'status-job-{job_no}')
        assert isinstance(label, Label)
        label.update(status)
        label.remove_class('hidden')
        label.add_class(cls)

    def log_error(self, label: str, ex: Exception) -> None:
        log = self.get_widget_by_id('test-job-errors')
        assert isinstance(log, RichLog)

        log.write(f'----------- {label} -----------')
        log.write(str(ex))
        log.write('')

    def focus_back_button(self) -> None:
        self.get_widget_by_id('btn-back').focus()

    def focus_continue_button(self) -> None:
        self.get_widget_by_id('btn-continue').focus()


class ErrorDialog(RunnableDialog[bool]):
    BINDINGS = [
        ('c', 'close', 'Close'),
        ('alt+c', 'close', 'Close')
    ]

    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self.title = title
        self.message = message

    def compose(self) -> ComposeResult:
        assert self.title is not None
        yield Vertical(
            Label(self.title, classes='header'),
            Label(self.message, classes='main-text', shrink=True, expand=True),
            Horizontal(
                ShortcutButton('&Close', variant='error', id='btn-close'),
                classes='action-area'
            ),
            id='error-dialog', classes='dialog error-dialog'
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.action_close()

    def action_close(self) -> None:
        self.set_result(True)


class KeyRequestDialog(ModalScreen[None]):
    BINDINGS = [
        ('c', 'cancel', 'Cancel'),
        ('alt+c', 'cancel', 'Cancel')
    ]

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label('Key request', classes='header'),
            Label('Please enter the following URL in a web browser:', classes='main-text'),
            Label(self.url, classes='main-text', id='key-request-url'),
            Label('Then follow the instructions the browser. The URL is valid for 10 minutes.',
                  classes='main-text', expand=True, shrink=True),
            Horizontal(
                ProgressBar(id='progress-indicator-indeterminate'),
                Label('Waiting', classes='main-text', id='status-label'),
            ),
            Horizontal(
                ShortcutButton('&Cancel', variant='error', id='btn-cancel'),
                classes='action-area'
            ),
            id='key-request-dialog', classes='dialog'
        )

    def update_status(self, status_str: str) -> None:
        status_label = self.get_widget_by_id('status-label')
        assert isinstance(status_label, Label)
        if status_str == 'initialized':
            pass
        elif status_str == 'seen':
            status_label.update('Page opened')
        elif status_str == 'email_sent':
            status_label.update('Email sent')
        elif status_str == 'verified':
            status_label.update('Email verified')

    @on(Button.Pressed, selector='#btn-cancel')
    def action_cancel(self) -> None:
        self.app.pop_screen()


class ExistingInstallConfirmDialog(RunnableDialog[str]):
    BINDINGS = [
        ('c', 'close', 'Close'),
        ('alt+c', 'close', 'Close')
    ]

    def __init__(self, method: str) -> None:
        super().__init__()
        self.method = method

    def compose(self) -> ComposeResult:
        assert self.method is not None
        yield Vertical(
            Label('Existing installation detected', classes='header'),
            Label(f'An existing {self.method} installation of the tests was detected. Continuing '
                  'will update the settings used by the existing installation.',
                  classes='main-text',
                  shrink=True, expand=True),
            Horizontal(
                ShortcutButton('&Quit', variant='error', id='btn-quit'),
                ShortcutButton('&Update', variant='warning', id='btn-update'),
                ShortcutButton('&Reinstall', variant='warning', id='btn-reinstall'),
                classes='action-area'
            ),
            id='replace-dialog', classes='dialog error-dialog'
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'btn-quit':
            self.set_result('quit')
        elif event.button.id == 'btn-update':
            self.set_result('update')
        else:
            self.set_result('reinstall')
