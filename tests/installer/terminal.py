import string
import sys

from enum import Enum
from typing import Callable

from rich.color import Color
from rich.style import StyleType


def add_alt_key_processing() -> None:
    from textual._ansi_sequences import ANSI_SEQUENCES_KEYS

    class MoreKeys(str, Enum):
        AltA = 'alt+a'
        AltB = 'alt+b'
        AltC = 'alt+c'
        AltD = 'alt+d'
        AltE = 'alt+e'
        AltF = 'alt+f'
        AltG = 'alt+g'
        AltH = 'alt+h'
        AltI = 'alt+i'
        AltJ = 'alt+j'
        AltK = 'alt+k'
        AltL = 'alt+l'
        AltM = 'alt+m'
        AltN = 'alt+n'
        AltO = 'alt+o'
        AltP = 'alt+p'
        AltQ = 'alt+q'
        AltR = 'alt+r'
        AltS = 'alt+s'
        AltT = 'alt+t'
        AltU = 'alt+u'
        AltV = 'alt+v'
        AltW = 'alt+w'
        AltX = 'alt+x'
        AltY = 'alt+y'
        AltZ = 'alt+z'

        AltShiftA = 'alt+shift+a'
        AltShiftB = 'alt+shift+b'
        AltShiftC = 'alt+shift+c'
        AltShiftD = 'alt+shift+d'
        AltShiftE = 'alt+shift+e'
        AltShiftF = 'alt+shift+f'
        AltShiftG = 'alt+shift+g'
        AltShiftH = 'alt+shift+h'
        AltShiftI = 'alt+shift+i'
        AltShiftJ = 'alt+shift+j'
        AltShiftK = 'alt+shift+k'
        AltShiftL = 'alt+shift+l'
        AltShiftM = 'alt+shift+m'
        AltShiftN = 'alt+shift+n'
        AltShiftO = 'alt+shift+o'
        AltShiftP = 'alt+shift+p'
        AltShiftQ = 'alt+shift+q'
        AltShiftR = 'alt+shift+r'
        AltShiftS = 'alt+shift+s'
        AltShiftT = 'alt+shift+t'
        AltShiftU = 'alt+shift+u'
        AltShiftV = 'alt+shift+v'
        AltShiftW = 'alt+shift+w'
        AltShiftX = 'alt+shift+x'
        AltShiftY = 'alt+shift+y'
        AltShiftZ = 'alt+shift+z'

    for c in string.ascii_lowercase:
        C = c.upper()
        ANSI_SEQUENCES_KEYS[f'\x1b{c}'] = (MoreKeys[f'Alt{C}'],)  # type: ignore
        ANSI_SEQUENCES_KEYS[f'\x1b{C}'] = (MoreKeys[f'AltShift{C}'],)  # type: ignore


def patch_borders() -> None:
    EXTRA_CELLS = frozenset(['\033(0' + c + '\033(1' for c in 'lqkxmja'])
    from rich import cells
    prev_cell_len = cells.cell_len

    def cell_len(text: str, _cell_len: Callable[[str], int] = cells.cached_cell_len) -> int:
        if text in EXTRA_CELLS:
            return 1
        elif '\033' in text:
            return len(text.replace('\033(0', '').replace('\033(1', ''))
        else:
            return prev_cell_len(text, _cell_len)

    cells.cell_len = cell_len
    cells.cached_cell_len = cell_len  # type: ignore

    BORDER = (
        ("\033(0l\033(1", "\033(0q\033(1", "\033(0k\033(1"),
        ("\033(0x\033(1",       " ",       "\033(0x\033(1"),  # noqa: E241
        ("\033(0m\033(1", "\033(0q\033(1", "\033(0j\033(1")
    )

    from textual import _border

    for t in ['round', 'solid', 'double', 'dashed', 'heavy', 'inner', 'outer', 'thick', 'tall',
              'panel', 'tab', 'wide']:
        _border.BORDER_CHARS[t] = BORDER  # type: ignore

    _border.BORDER_CHARS['tall'] = ((" ", " ", " "), (" ", " ", " "), (" ", " ", " "))
    _border.BORDER_CHARS['outer'] = ((" ", " ", " "), (" ", " ", " "), (" ", ".", "."))

    _border.BORDER_CHARS['vkey'] = (
        ("\033(0l\033(1", " ", "\033(0k\033(1"),
        ("\033(0x\033(1", " ", "\033(0x\033(1"),
        ("\033(0m\033(1", " ", "\033(0j\033(1")
    )

    _border.BORDER_CHARS['hkey'] = (
        ("\033(0l\033(1", "\033(0q\033(1", "\033(0k\033(1"),
        (" ", " ", " "),
        ("\033(0m\033(1", "\033(0q\033(1", "\033(0j\033(1")
    )


def patch_toggle_button(unicode: bool) -> None:
    from textual.widgets._toggle_button import ToggleButton
    from textual.widgets._radio_button import RadioButton
    from textual.content import Content
    from textual.style import Style

    class PatchedToggleButton(ToggleButton):
        @property
        def _button(self) -> Content:
            button_style = self.get_visual_style("toggle--button")
            side_style = Style(self.colors[3],
                               self.background_colors[1])
            return Content.assemble(
                (self.BUTTON_LEFT, side_style),
                (self.BUTTON_INNER, button_style),
                (self.BUTTON_RIGHT, side_style)
            )
    ToggleButton._button = PatchedToggleButton._button  # type: ignore
    RadioButton._button = PatchedToggleButton._button  # type: ignore

    if not unicode:
        ToggleButton.BUTTON_LEFT = '['
        ToggleButton.BUTTON_RIGHT = ']'
        ToggleButton.BUTTON_INNER = 'x'
        RadioButton.BUTTON_LEFT = '('
        RadioButton.BUTTON_INNER = '\033(0`\033(1'
        RadioButton.BUTTON_RIGHT = ')'

    from textual.widgets import _rule

    _rule._HORIZONTAL_LINE_CHARS['solid'] = '\033(0q\033(1'


def patch_scrollbar(unicode: bool) -> None:
    from textual.scrollbar import ScrollBarRender
    from rich.segment import Segment, Segments
    from rich.style import Style

    if unicode:
        VERTICAL_BAR = ' '
        HORIZONTAL_BAR = ' '
    else:
        VERTICAL_BAR = ' '
        HORIZONTAL_BAR = ' '

    class SBRenderer(ScrollBarRender):

        def __init__(self, virtual_size: int = 100, window_size: int = 0, position: float = 0,
                     thickness: int = 1, vertical: bool = True,
                     style: StyleType = "bright_magenta on #555555") -> None:
            super().__init__(virtual_size, window_size, position, thickness, vertical, style)

        @classmethod
        def render_bar(cls, size: int = 25, virtual_size: float = 50, window_size: float = 20,
                       position: float = 0, thickness: int = 1, vertical: bool = True,
                       back_color: Color = Color.parse("#555555"),
                       bar_color: Color = Color.parse("bright_magenta")) -> Segments:
            if vertical:
                bar = VERTICAL_BAR
            else:
                bar = HORIZONTAL_BAR
            if window_size and size and virtual_size and size != virtual_size:
                thumb_size = int(window_size / virtual_size * size)
                if thumb_size < 1:
                    thumb_size = 1
                position = (size - thumb_size) * position / (virtual_size - window_size)
                top_size = int(position)
                bottom_size = size - top_size - thumb_size

                upper_segment = Segment(bar, Style(bgcolor=back_color, color=bar_color,
                                                   meta={'@mouse.up': 'scroll_up'}))
                lower_segment = Segment(bar, Style(bgcolor=back_color, color=bar_color,
                                                   meta={'@mouse.up': 'scroll_down'}))
                thumb_segment = Segment(' ', Style(color=bar_color, reverse=True))
                segments = ([upper_segment] * top_size + [thumb_segment] * thumb_size
                            + [lower_segment] * bottom_size)
            else:
                segments = [Segment(bar, Style(bgcolor=back_color))] * size

            if vertical:
                return Segments(segments, new_lines=True)
            else:
                return Segments(segments, new_lines=False)

    ScrollBarRender.render_bar = SBRenderer.render_bar  # type: ignore


def patch_markdown() -> None:
    from textual.widgets import Markdown

    Markdown.BULLETS = ['\033(0`\033(1', '*', '-', 'o']


def patch_select() -> None:
    from textual.widgets import _select
    from textual.widgets import Static

    def compose(self):  # type: ignore
        yield Static(self.placeholder, id='label')
        yield Static("_", classes='arrow down-arrow')
        yield Static("^", classes='arrow up-arrow')

    _select.SelectCurrent.compose = compose  # type: ignore


def patch_progress_bar() -> None:
    from textual.app import ComposeResult, RenderResult
    from textual.widgets import ProgressBar
    from textual.widgets._progress_bar import Bar

    class BR:
        def __init__(self, br: RenderResult) -> None:
            self.br = br

        def __rich_console__(self, console, options):  # type: ignore
            r = next(self.br.__rich_console__(console, options))  # type: ignore
            for seg in r.render(console, options):
                yield seg._replace(text=''.join(['\033(0q\033(1'] * len(str(seg[0]))), style=seg[1])

    class PatchedBar(Bar):
        def render(self) -> RenderResult:
            br = super().render()
            return BR(br)

    def compose(self: Bar) -> ComposeResult:
        yield PatchedBar(id='bar', clock=self._clock).data_bind(
            ProgressBar.percentage).data_bind(ProgressBar.gradient)

    ProgressBar.compose = compose  # type: ignore


_LASTC = ''


def _expect(c: str) -> None:
    global _LASTC
    if _LASTC != '':
        r = _LASTC
        _LASTC = ''
    else:
        r = sys.stdin.read(1)
    if r != c:
        raise Exception('Unexpected terminal response: %s' % r)


def _readnum() -> int:
    global _LASTC
    s = ''
    while True:
        c = sys.stdin.read(1)
        if c.isdigit():
            s += c
        else:
            _LASTC = c
            return int(s)


_TERMINAL_SUPPORTS_UNICODE = None


def terminal_supports_unicode() -> bool:
    global _TERMINAL_SUPPORTS_UNICODE
    if _TERMINAL_SUPPORTS_UNICODE is not None:
        return _TERMINAL_SUPPORTS_UNICODE
    try:
        import termios
        initial_mode = termios.tcgetattr(sys.stdin)
        mode = termios.tcgetattr(sys.stdin)
        mode[3] &= ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, mode)
        try:
            # save cursor, move to col 0, print unicode char, report position, restore cursor
            print('\0337\033[0G─\033[6n\0338', end='', flush=True)
            _expect('\033')
            _expect('[')
            _ = _readnum()
            _expect(';')
            x = _readnum()
            _expect('R')
            _TERMINAL_SUPPORTS_UNICODE = x == 2
            print('   ')
            return _TERMINAL_SUPPORTS_UNICODE
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, initial_mode)
    except ImportError:
        print('Cannot import termios')
        raise


def patch_rich_terminals() -> None:
    from rich import console
    from rich.color import ColorSystem
    console._TERM_COLORS['rxvt'] = ColorSystem.EIGHT_BIT


def run_patches() -> None:
    unicode = terminal_supports_unicode()
    if not unicode:
        patch_borders()
        patch_select()
        patch_progress_bar()
        patch_markdown()

    patch_scrollbar(unicode)
    patch_toggle_button(unicode)

    add_alt_key_processing()
    patch_rich_terminals()


run_patches()
