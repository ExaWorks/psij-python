import asyncio
from typing import Optional

from ..dialogs import KeyRequestDialog, ProgressDialog, ErrorDialog
from ..log import log
from .panel import Panel
from ..state import KEY_PATH
from ..widgets import ShortcutButton

from textual import on
from textual.containers import Vertical, Horizontal
from textual.widget import Widget
from textual.widgets import Input, Label, MaskedInput, Button


class KeyPanel(Panel):
    def _build_widgets(self) -> Widget:
        self.email_input = Input(placeholder='Enter email', id='key-email-input')
        self.request_button = ShortcutButton('&Request key', id='btn-request-key')
        return Vertical(
            Label('Dashboard authentication key', classes='header'),
            Label('A key associates your test result uploads with a verified email and allows us '
                  'to prevent unauthorized uploads.',
                  classes='help-text', shrink=True, expand=True),
            Label(f'A valid key was found in {KEY_PATH}', classes='p-l m-b -success hidden',
                  id='msg-auth-key-valid', shrink=True, expand=True),
            Label(f'No key was found in {KEY_PATH}', classes='p-l m-b -error hidden',
                  id='msg-auth-key-not-found', shrink=True, expand=True),
            Label(f'Invalid key found in {KEY_PATH}', classes='p-l m-b -error hidden',
                  id='msg-auth-key-invalid', shrink=True, expand=True),
            Vertical(
                Label('Your email address:', classes='form-label'),
                Horizontal(
                    self.email_input,
                    self.request_button
                ),
                classes='form-row h-auto', id='key-email-input-group'
            ),
            Vertical(
                Label('Or enter a key below:', classes='form-label'),
                MaskedInput(template='NNNNNNNNNNNNNNNN:NNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN',  # noqa: E501
                            id='key-input'),
                Label('', classes='form-label -error', id='key-check-error'),
                classes='form-row h-auto', id='key-input-group'
            ),
            classes='panel'
        )

    @property
    def label(self) -> str:
        return 'Key'

    @property
    def name(self) -> str:
        return 'key'

    def _show_message(self, id: str) -> None:
        for i in ['msg-auth-key-valid', 'msg-auth-key-invalid', 'msg-auth-key-not-found']:
            if i == id:
                self.get_widget_by_id(i).set_class(False, 'hidden')
            else:
                self.get_widget_by_id(i).set_class(True, 'hidden')

    async def activate(self) -> None:
        if self.state.has_key and self.state.key_is_valid is None:
            log.write('Verifying key...\n')
            self.state.key_is_valid = await self.verify_key()
        input_active = self.update()
        if self.email_input.value == '':
            maintainer_email = self.state.conf['maintainer_email']
            log.write(f'No email, setting to maintainer email: {maintainer_email}\n')
            self.email_input.value = maintainer_email
        if input_active:
            self.email_input.focus(False)

    @on(Button.Pressed, '#btn-request-key')
    def action_request_key(self) -> None:
        email_input = self.get_widget_by_id('key-email-input')
        assert isinstance(email_input, Input)
        email = email_input.value
        asyncio.create_task(self.request_key(email))

    @on(Input.Submitted, '#key-email-input')
    def key_email_submitted(self) -> None:
        btn = self.get_widget_by_id('btn-request-key')
        btn.focus()

    @on(Input.Changed, '#key-input')
    def key_input_changed(self) -> None:
        # remove error message
        self._set_key_check_error('')
        self.get_widget_by_id('key-input').remove_class('invalid')

    @on(Input.Submitted, '#key-input')
    async def key_submitted(self, event: Input.Changed) -> None:
        key = event.value
        try:
            valid = await self.verify_key(key)
            self.get_widget_by_id('key-input').set_class(not valid, 'invalid')
            if not valid:
                self._set_key_check_error('Invalid key.')
            else:
                self._set_key_check_error('')
                self._key_received(key)
                self.update()
        except Exception as ex:
            log.write(f'Ex: {ex}\n')

    def _set_key_check_error(self, text: str) -> None:
        key_check_error = self.get_widget_by_id('key-check-error')
        assert isinstance(key_check_error, Label)
        key_check_error.update(text)

    def _key_received(self, key: str) -> None:
        with open(KEY_PATH, 'w') as f:
            f.write(key)
        self.state.has_key = True
        self.state.key_is_valid = True
        self.app._focus_next()  # type: ignore

    def update(self) -> bool:
        input_active = True
        if self.state.has_key:
            if self.state.key_is_valid:
                self._show_message('msg-auth-key-valid')
                input_active = False
            else:
                self._show_message('msg-auth-key-invalid')
        else:
            self._show_message('msg-auth-key-not-found')

        self.get_widget_by_id('key-email-input-group').disabled = not input_active
        self.get_widget_by_id('key-input-group').disabled = not input_active
        return input_active

    async def verify_key(self, key: Optional[str] = None) -> bool:
        if not key:
            key = self.state.key
        if key is None:
            return False
        # some offline quick validation
        if len(key) != 65:
            return False
        cix = key.find(':')
        if cix != 16:
            return False

        self.app.push_screen(ProgressDialog('Verifying key...'))
        try:
            result = await self.state.request('/authVerifyKey', {'key': key}, 'Key verification',
                                              self.display_error_dialog)
            if result:
                success = result['success']
                assert isinstance(success, bool)
                return success
        finally:
            self.app.pop_screen()
        return False

    async def request_key(self, email: str) -> None:
        key = await self._key_request(email)
        if key:
            self._key_received(key)
            self.update()

    async def _key_request(self, email: str) -> Optional[str]:
        self.app.push_screen(ProgressDialog('Initializing request...'))
        try:
            result = await self.state.request('/keyRequestInit', {'email': email},
                                              'Key request initialization',
                                              self.display_error_dialog)
        finally:
            self.app.pop_screen()
        if not result:
            return None
        request_id = result['id']
        assert isinstance(request_id, str)
        base_url = self.state.conf['server_url']
        d = KeyRequestDialog(f'{base_url}/auth/{request_id}')
        self.app.push_screen(d)
        try:
            return await self._run_key_request_loop(request_id, d)
        finally:
            log.write('Key request loop done\n')
            self.app.pop_screen()

    async def _run_key_request_loop(self, request_id: str, d: KeyRequestDialog) -> Optional[str]:
        while d.is_active:
            result = await self.state.request('/keyRequestStatus', {'id': request_id},
                                              'Key request status check',
                                              self.display_error_dialog)
            log.write(f'Result: {result}\n')
            if not result:
                return None

            success = result['success']

            if not success:
                error = result['error']
                assert isinstance(error, str)
                ed = ErrorDialog('Error requesting key', error)
                await ed.run(self.app)
                return None
            else:
                status = result['status']
                assert isinstance(status, str)
                d.update_status(status)
                if status == 'verified':
                    return result['key']  # type: ignore
                await asyncio.sleep(5)
        return None

    async def validate(self) -> bool:
        if not self.state.key_is_valid:
            email_valid = self.email_input.value != ''
            self.email_input.set_class(not email_valid, 'invalid', update=True)
        else:
            self.email_input.set_class(False, 'invalid', update=True)
        self.request_button.set_class(not self.state.key_is_valid, 'invalid', update=True)
        assert self.state.key_is_valid is not None
        return self.state.key_is_valid

    async def display_error_dialog(self, title: str, message: str) -> None:
        try:
            d = ErrorDialog(title, message)
            await d.run(self.app)
        except Exception as ex:
            log.write(f'caught {ex}\n')
