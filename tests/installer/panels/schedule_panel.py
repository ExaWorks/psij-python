from typing import cast

from .panel import Panel

from textual.containers import Vertical, Horizontal
from textual.widget import Widget
from textual.widgets import Label, RadioSet, RadioButton, TextArea

from ..dialogs import ErrorDialog
from ..log import log
from ..install_methods import METHODS, InstallMethod


class MRadioSet(RadioSet):
    BINDINGS = [
        ('enter,space', 'select')
    ]

    def __init__(self, panel: 'SchedulePanel', *radios: RadioButton, id: str | None = None) -> None:
        super().__init__(*radios, id=id)
        self.panel = panel

    def watch__selected(self) -> None:
        super().watch__selected()
        if self._selected is not None:
            self.panel.radio_focused(cast(RadioButton, self.children[self._selected]))

    def watch_has_focus(self, value: bool) -> None:
        if not value:
            self.panel.radio_focused(None)
        super().watch_has_focus(value)

    def action_select(self) -> None:
        if self._selected is not None:
            selected = self.children[self._selected]
            assert isinstance(selected, RadioButton)
            if selected.value:
                self.app._focus_next()  # type: ignore

        self.action_toggle_button()

    def get_selected_index(self) -> int | None:
        return self._selected


class SchedulePanel(Panel):
    def _build_widgets(self) -> Widget:
        radios = []
        labels = []

        for m in METHODS:
            available, msg = m.is_available()
            if msg is None:
                msg = ''
            radios.append(RadioButton(m.label, id=f'btn-{m.name}', disabled=not available))
            labels.append(Label(msg, id=f'label-{m.name}'))
        labels_container = Vertical(*labels, id='method-status', classes='h-auto')

        return Vertical(
            Label('Install', classes='header'),
            Label('This step schedules the tests to be run daily.',
                  classes='help-text', shrink=True, expand=True),
            Vertical(
                Label('Installation method:', classes='form-label'),
                Horizontal(
                    MRadioSet(self, *radios, id='rs-method'),
                    labels_container,
                    classes='h-auto'
                ),
                classes='h-auto m-b-1'
            ),
            Vertical(
                Label('Preview', classes='form-label'),
                TextArea('-', id='method-preview', classes='', language='bash',
                         read_only=True, disabled=True),
                classes='form-row h-auto'
            ),
            classes='panel'
        )

    @property
    def label(self) -> str:
        return 'Install'

    @property
    def name(self) -> str:
        return 'install'

    def _get_selected_method(self) -> InstallMethod | None:
        radio_set = self.get_widget_by_id('rs-method')
        assert isinstance(radio_set, MRadioSet)
        selected_index = radio_set.get_selected_index()
        if selected_index is None:
            return None
        return METHODS[selected_index]

    async def validate(self) -> bool:
        try:
            m = self._get_selected_method()
            assert m is not None
            self.state.install_method = m
            m.install()
            if m.name == 'custom':
                self.app.copy_to_clipboard(m.preview)
            return True
        except Exception as ex:
            await ErrorDialog('Error scheduling tests', str(ex)).run(self.app)
            return False

    async def activate(self) -> None:
        self.get_widget_by_id('rs-method').focus(scroll_visible=False)
        for btn in self.query('RadioButton'):
            if not btn.disabled:
                assert isinstance(btn, RadioButton)
                btn.value = True
                break

    def radio_focused(self, btn: RadioButton | None) -> None:
        log.write(f'focused {btn}\n')
        preview = self.get_widget_by_id('method-preview')
        assert isinstance(preview, TextArea)

        if btn is not None:
            assert btn.id is not None
            name = btn.id.split('-')[-1]
            for m in METHODS:
                if m.name == name:
                    preview.text = m.preview
                    return
