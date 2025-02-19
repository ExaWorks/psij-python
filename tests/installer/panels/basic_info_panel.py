import random
import socket
import string

from .panel import Panel
from ..log import log
from ..widgets import ShortcutButton, MInput

from textual import on
from textual.containers import Vertical, Horizontal
from textual.widget import Widget
from textual.widgets import Input, Label, Button


FQDN = socket.getfqdn()


class BasicInfoPanel(Panel):
    def _build_widgets(self) -> Widget:
        self.name_input = MInput(placeholder='Enter machine name', id='name-input')
        self.email_input = MInput(placeholder='Enter email', id='email-input')
        return Vertical(
            Label('Some basic information', classes='header'),
            Label('The name should be something descriptive, such as '
                  '"aurora.alcf.anl.gov". This name will be displayed on the online testing '
                  'dashboard.', classes='help-text media-large', shrink=True, expand=True),
            Vertical(
                Label('Machine name (e.g. echo.example.net):', classes='form-label'),
                Horizontal(
                    self.name_input,
                    ShortcutButton('Use &FQDN', id='btn-use-fqdn'),
                    id='name-input-group'
                ),
                classes='form-row h-auto'
            ),
            Label('Your email allows us to contact you if we need more information about failing '
                  'tests. It does not appear publicly on the dashboard.',
                  classes='help-text', shrink=True, expand=True),
            Vertical(
                Label('Maintainer email:', classes='form-label'),
                self.email_input,
                classes='form-row h-auto'
            ),
            classes='panel'
        )

    @property
    def label(self) -> str:
        return 'Basic info'

    @property
    def name(self) -> str:
        return 'basic-info'

    async def activate(self) -> None:
        log.write('Activate basic info panel\n')
        if self.name_input.value == '':
            conf_name = self.state.conf['id']
            log.write(f'Conf name: {conf_name}\n')
            val = None
            if conf_name == 'hostname':
                val = FQDN
            elif conf_name == 'random':
                val = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            elif len(conf_name) > 0 and conf_name[0] == '"' and conf_name[-1] == '"':
                val = conf_name[1:-1]
            else:
                val = ''
            assert val is not None
            self.name_input.value = val
        if self.email_input.value == '':
            self.email_input.value = self.state.conf['maintainer_email']
        self.name_input.disabled = False
        self.name_input.focus(False)

    async def validate(self) -> bool:
        log.write(f'name value: {self.name_input.value}\n')
        name_valid = self.name_input.value != ''
        self.name_input.set_class(not name_valid, 'invalid', update=True)

        if name_valid:
            self.state.update_conf('id', self.name_input.value)
        if self.email_input.value:
            self.state.update_conf('maintainer_email', self.email_input.value)
        return name_valid

    @on(Input.Submitted, '#name-input')
    def name_submitted(self) -> None:
        email = self.get_widget_by_id('email-input')
        email.focus(False)

    @on(Input.Submitted, '#email-input')
    def email_submitted(self) -> None:
        self.app._focus_next()  # type: ignore

    @on(Button.Pressed, '#btn-use-fqdn')
    def use_fqdn_pressed(self) -> None:
        name_input = self.get_widget_by_id('name-input')
        assert isinstance(name_input, Input)
        name_input.value = FQDN
