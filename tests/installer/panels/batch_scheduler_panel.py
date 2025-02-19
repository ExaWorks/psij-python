import asyncio
import re
from typing import Tuple, Optional, cast

from psij import JobExecutor, Job, JobSpec, ResourceSpecV1, JobAttributes, JobState
from .panel import Panel
from ..dialogs import TestJobsDialog
from ..log import log
from ..state import Attr, State
from ..widgets import MSelect, ShortcutButton

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Label, Input, Button, TextArea, Checkbox, Select


class EditAttrsScreen(ModalScreen[None]):
    BINDINGS = [
        ('F1', 'context_help', 'Help'),
        ('down', 'input_down'),
        ('up', 'input_up'),
        ('c', 'cancel'),
        ('alt+c', 'cancel'),
        ('a', 'apply'),
        ('alt+a', 'apply'),
        ('ctrl+q', 'quit')
    ]

    def __init__(self, panel: 'BatchSchedulerPanel') -> None:
        super().__init__()
        self.panel = panel
        self.state = panel.state

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label('Edit custom attributes.',
                  classes='header', shrink=True, expand=True),
            Label('If your scheduler requires non-standard parameters (e.g., "constraint=knl"), '
                  'enter them here.',
                  classes='help-text', shrink=True, expand=True),
            Vertical(
                Horizontal(
                    Label('Name', classes='th'),
                    Label('Value', classes='th'),
                    Label('Filter', classes='th'),
                    classes='attr-header h-auto'
                ),
                self._make_row(0)[0],
                id='attr-rows', classes='attrs'
            ),
            Horizontal(
                Button('[b bright_yellow]C[/b bright_yellow]lose', variant='error',
                       id='btn-attrs-cancel', classes='m-r-1'),
                Button('[b bright_yellow]A[/b bright_yellow]pply', variant='primary',
                       id='btn-attrs-apply', classes='m-r'),
                classes='action-area'
            ),
            id='edit-attrs-dialog', classes='dialog'
        )

    def _make_row(self, index: int) -> Tuple[Widget, Input, Input, Input]:
        name = Input('', id=f'attr-name-{index}', classes='attr-name td')
        value = Input('', id=f'attr-value-{index}', classes='attr-value td')
        filter = Input('', id=f'attr-filter-{index}', classes='attr-filter td')
        return Horizontal(name, value, filter, classes='attr-row h-auto'), name, value, filter

    def _get_row(self, input: Input) -> int:
        id = input.id
        assert id is not None
        return int(id.split('-')[-1])

    def action_input_down(self) -> None:
        self._move_input_focus(1)

    def action_input_up(self) -> None:
        self._move_input_focus(-1)

    def _move_input_focus(self, d: int) -> None:
        q = self.query('*:focus')
        if len(q) > 0:
            focused = q.first()
            if focused.has_class('td'):
                id = focused.id
                assert id is not None
                id_parts = id.split('-')
                index = int(id_parts[-1])
                q2 = self.query('#' + '-'.join(id_parts[:-1]) + '-' + str(index + d))
                if len(q2) > 0:
                    q2.first().focus()
                else:
                    self.get_widget_by_id('btn-attrs-apply').focus()
            else:
                if focused.id == 'btn-attrs-apply':
                    if d == 1:
                        self.get_widget_by_id('attr-name-0').focus()
                    else:
                        self.get_widget_by_id('attr-rows').children[-1].children[0].focus()

    @on(Input.Submitted, '.attr-name')
    def name_submitted(self, event: Input.Submitted) -> None:
        log.write(f'input submitted {event.input.id}\n')
        event.input.remove_class('invalid')
        assert event.input.parent is not None
        if event.input.value != '':
            self._ensure_row(self._get_row(event.input) + 1)
        event.input.parent.children[1].focus()

    @on(Input.Submitted, '.attr-value')
    def value_submitted(self, event: Input.Submitted) -> None:
        event.input.remove_class('invalid')
        assert event.input.parent is not None
        if event.input.value != '':
            self._ensure_row(self._get_row(event.input) + 1)
        event.input.parent.children[2].focus()

    @on(Input.Submitted, '.attr-filter')
    def filter_submitted(self, event: Input.Submitted) -> None:
        event.input.remove_class('invalid')
        row = self._get_row(event.input)
        if event.input.value != '':
            self._ensure_row(row + 1)
        next_name = self.query(f'#attr-name-{row + 1}')
        if next_name:
            next_name.focus()
        else:
            self.get_widget_by_id('btn-attrs-apply').focus()

    def _ensure_row(self, row: int) -> Tuple[Input, Input, Input]:
        next_name = self.query(f'#attr-name-{row}')
        if not next_name:
            rows = self.get_widget_by_id('attr-rows')
            row_widget, name, value, filter = self._make_row(row)
            rows.mount(row_widget)
        else:
            row_widget = self.get_widget_by_id('attr-rows').children[row + 1]
            name = cast(Input, row_widget.children[0])
            value = cast(Input, row_widget.children[1])
            filter = cast(Input, row_widget.children[2])
        return name, value, filter

    def on_mount(self) -> None:
        ix = 0
        for attr in self.state.attrs:
            name_input, value_input, filter_input = self._ensure_row(ix)
            name_input.value = attr.name
            value_input.value = attr.value
            if attr.filter != '.*':
                filter_input.value = attr.filter
            ix += 1

    def action_quit(self) -> None:
        self.app.exit()

    def action_apply(self) -> None:
        if self._validate_and_commit():
            self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, '#btn-attrs-apply')
    def apply_pressed(self) -> None:
        self.action_apply()

    @on(Button.Pressed, '#btn-attrs-cancel')
    def cancel_pressed(self) -> None:
        self.action_cancel()

    def _tag_input(self, is_valid: bool, input: Input,
                   first_invalid: Optional[Input]) -> Optional[Input]:
        if not is_valid:
            input.add_class('invalid')
            if first_invalid is None:
                return input
        return first_invalid

    def _re_valid(self, restr: str) -> bool:
        try:
            re.compile(restr)
            return True
        except Exception:
            return False

    def _validate_and_commit(self) -> bool:
        rows = self.get_widget_by_id('attr-rows')
        attrs = []
        first_invalid = None
        for row_index in range(1, len(rows.children)):
            row = rows.children[row_index]
            name = row.children[0]
            value = row.children[1]
            filter = row.children[2]
            assert (isinstance(name, Input) and isinstance(value, Input)
                    and isinstance(filter, Input))
            if name.value == '' and value.value == '' and filter.value == '':
                continue
            # at least one set
            name_valid = name.value != ''
            value_valid = value.value != ''
            filter_valid = filter.value == '' or self._re_valid(filter.value)
            first_invalid = self._tag_input(name_valid, name, first_invalid)
            first_invalid = self._tag_input(value_valid, value, first_invalid)
            first_invalid = self._tag_input(filter_valid, filter, first_invalid)
            if name_valid and value_valid and filter_valid:
                attrs.append(Attr(filter.value, name.value, value.value))
        if first_invalid is None:
            self.state.set_custom_attrs(attrs)
            self.panel.update_attrs()
        else:
            first_invalid.focus()
        return first_invalid is None


class BatchSchedulerPanel(Panel):
    BINDINGS = [
        ('t', 'toggle_test_job'),
        ('alt+t', 'toggle_test_job')
    ]

    def __init__(self, state: State) -> None:
        super().__init__(state)
        self._auto_scheduler: Optional[str] = None

    def _build_widgets(self) -> Widget:
        return Vertical(
            Label('Select and configure a batch system.', classes='header'),
            Vertical(
                Label('Your system does not appear to have a batch scheduler. If you are certain '
                      'that this is wrong, you can select one below. If not, tests will be run '
                      'using non-batch executors.', classes='help-text media-large',
                      shrink=True, expand=True),
                id='warn-no-batch'
            ),
            Horizontal(
                Vertical(
                    Label('Batch system:', classes='form-label'),
                    MSelect(
                        [('Select...', 'none'), ('Local only', 'local'), ('Slurm', 'slurm'),
                         ('PBS', 'pbs'), ('LSF', 'lsf'), ('Cobalt', 'cobalt')],
                        id='batch-selector',
                        allow_blank=False),
                    classes='bs-col-1 form-row', id='batch-selector-col'
                ),
                Vertical(
                    Label('Account/project:', classes='form-label'),
                    Input(id='account-input'),
                    classes='bs-col-2 form-row batch-valid'
                ),
                classes='w-100 form-row', id='batch-system-group-1'
            ),
            Horizontal(
                Vertical(
                    Label('Queue:', classes='form-label'),
                    Input(id='queue-input'),
                    classes='bs-col-1 form-row batch-valid'
                ),
                Vertical(
                    Label('Multi-node queue:', classes='form-label'),
                    Input(id='mqueue-input'),
                    classes='bs-col-2 form-row batch-valid'
                ),
                Checkbox('Run [b bright_yellow]t[/b bright_yellow]est job', value=False,
                         id='cb-run-test-job', classes='bs-col-3 m-t-1 batch-valid'),
                classes='w-100 form-row', id='batch-system-group-2'
            ),
            Horizontal(
                Vertical(
                    Label('Custom attributes:', classes='form-label'),
                    ShortcutButton('&Edit attrs.', id='btn-edit-attrs'),
                    classes='bs-col-1 h-auto'
                ),
                Vertical(
                    TextArea('', id='custom-attrs', read_only=True, soft_wrap=False),
                    classes='bs-col-23 h-auto'
                ),
                classes='w-100 h-auto batch-valid'
            ),
            classes='panel'
        )

    async def validate(self) -> bool:
        run_test_job = self.get_widget_by_id('cb-run-test-job')
        assert isinstance(run_test_job, Checkbox)
        scheduler = self._get_scheduler()

        if run_test_job.value and scheduler != 'none' and scheduler != 'local':
            return await self.run_test_jobs()
        else:
            return True

    @property
    def label(self) -> str:
        return 'Scheduler'

    @property
    def name(self) -> str:
        return 'scheduler'

    def _get_scheduler(self) -> str:
        selector = self.get_widget_by_id('batch-selector')
        assert isinstance(selector, Select)
        value = selector.selection
        assert isinstance(value, str)
        return value

    async def activate(self) -> None:
        self.update_attrs()
        scheduler = self._get_scheduler()
        if scheduler is None or scheduler == 'none':
            self.get_widget_by_id('batch-selector').focus(False)
        elif scheduler == 'local':
            self.app._focus_next()  # type: ignore
        else:
            self.get_widget_by_id('account-input').focus(False)

    def update_attrs(self) -> None:
        s = ''
        for attr in self.state.attrs:
            if attr.filter == '.*':
                s += f'{attr.name}: {attr.value}\n'
            else:
                s += f'{attr.name}: {attr.value} ({attr.filter})\n'
        control = self.get_widget_by_id('custom-attrs')
        assert isinstance(control, TextArea)
        control.text = s

    @on(Select.Changed, '#batch-selector')
    def batch_system_selected(self) -> None:
        scheduler = self._get_scheduler()

        self.state.set_batch_executor(scheduler)

        disabled = (scheduler is None or scheduler == 'none' or scheduler == 'local')
        for widget in self.query('.batch-valid'):
            widget.disabled = disabled
        run_test_job = self.get_widget_by_id('cb-run-test-job')
        assert isinstance(run_test_job, Checkbox)
        run_test_job.value = not disabled
        if scheduler == 'local':
            self.app._focus_next()  # type: ignore
        else:
            self.get_widget_by_id('account-input').focus(False)

    def set_scheduler(self, name: str) -> None:
        if name == '':
            name = 'none'
        selector = self.get_widget_by_id('batch-selector')
        assert isinstance(selector, Select)
        selector.value = name
        self._auto_scheduler = name

    @on(Input.Submitted, '#account-input')
    def account_submitted(self, event: Input.Submitted) -> None:
        self.state.update_conf('account', event.value)
        next = self.get_widget_by_id('queue-input')
        next.focus(False)

    @on(Input.Submitted, '#queue-input')
    def queue_submitted(self, event: Input.Submitted) -> None:
        self.state.update_conf('queue_name', event.value)
        next = self.get_widget_by_id('mqueue-input')
        assert isinstance(next, Input)
        if next.value == '':
            next.value = event.input.value
            self.state.update_conf('multi_node_queue_name', event.value)
        next.focus(False)

    @on(Input.Submitted, '#mqueue-input')
    def mqueue_submitted(self, event: Input.Submitted) -> None:
        self.state.update_conf('multi_node_queue_name', event.value)
        self.app._focus_next()  # type: ignore

    @on(Button.Pressed, '#btn-edit-attrs')
    def action_edit_attrs(self) -> None:
        if not self.active or self.state.scheduler is None:
            return
        self.app.push_screen(EditAttrsScreen(self))

    def action_toggle_test_job(self) -> None:
        cb = self.get_widget_by_id('cb-run-test-job')
        if not self.active or self.state.scheduler is None:
            return
        assert isinstance(cb, Checkbox)
        cb.value = not cb.value

    @on(Checkbox.Changed, '#cb-run-test-job')
    def action_cb_test_job_changed(self, event: Checkbox.Changed) -> None:
        self.run_test_job = event.checkbox.value

    async def run_test_jobs(self) -> bool:
        jd = TestJobsDialog()
        self.app.push_screen(jd)
        # without this, the widgets in TestJobsDialog do not seem to be accessible
        await asyncio.sleep(0.1)
        j1 = await self._run_test_job(jd, 1, 'Single node job', None, '')
        j2 = await self._run_test_job(jd, 2, 'Multi node job ', ResourceSpecV1(node_count=4),
                                      f'test_nodefile[{self.state.scheduler}:multiple')

        if j1 and j2:
            jd.focus_continue_button()
        else:
            jd.focus_back_button()

        return await jd.wait()

    async def _run_test_job(self, jd: TestJobsDialog, job_no: int, label: str,
                            rspec: Optional[ResourceSpecV1], test_name: str) -> bool:
        try:
            jd.set_running(job_no)
            await asyncio.sleep(0.5)
            job = self._launch_job(test_name, rspec)

            await self._wait_for_queued_state(job)
            try:
                job.cancel()
            except Exception as ex:
                log.write(f'Failed to cancel job: {ex}')
            jd.set_status(job_no, 'OK', 'status-succeeded')
            return True
        except Exception as ex:
            jd.log_error(label, ex)
            jd.set_status(job_no, 'Failed', 'status-failed')
            return False

    def _launch_job(self, test_name: str, rspec: Optional[ResourceSpecV1]) -> Job:
        scheduler = self._get_scheduler()
        assert scheduler is not None

        ex = JobExecutor.get_instance(scheduler)

        attrs = JobAttributes()

        account = self.state.conf.get('account', '')
        if rspec is not None and rspec.computed_node_count > 1:
            queue = self.state.conf.get('multi_node_queue_name', '')
        else:
            queue = self.state.conf.get('queue_name', '')
        if account != '':
            attrs.account = account
        if queue != '':
            attrs.queue_name = queue
        for attr in self.state.attrs:
            if re.match(attr.filter, test_name):
                attrs.set_custom_attribute(attr.name, attr.value)
        log.write(f'attrs: {attrs}, rspec: {rspec}\n')
        job = Job(JobSpec('/bin/date', attributes=attrs, resources=rspec))
        ex.submit(job)
        log.write('Job submitted\n')
        return job

    async def _wait_for_queued_state(self, job: Job) -> None:
        while True:
            status = job.status
            log.write(f'Job status: {status}\n')
            state = status.state
            if state == JobState.QUEUED or state.is_greater_than(JobState.QUEUED):
                if state == JobState.FAILED:
                    raise Exception(status.message)
                return
            await asyncio.sleep(0.2)
