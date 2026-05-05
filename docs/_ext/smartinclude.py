from docutils.parsers.rst import directives
from docutils.nodes import Node
from sphinx.directives.code import LiteralInclude
from typing import TYPE_CHECKING, Dict, Any, List

if TYPE_CHECKING:
    from sphinx.application import Sphinx

class SmartInclude(LiteralInclude):
    option_spec = LiteralInclude.option_spec | {'section': directives.unchanged_required}

    def run(self) -> List[Node]:
        rel_filename, filename = self.env.relfn2path(self.arguments[0])
        if 'section' in self.options:
            section = ' ' + self.options['section']
        else:
            section = ''

        start_line = f'# DOC: start{section}'
        end_line = f'# DOC: end{section}'

        lines = []
        on = False
        dedent = 0
        with open(filename, 'r') as f:
            lineno = 1
            for line in f:
                line2 = line.strip()
                if line2 == start_line:
                    on = True
                    dedent = line.index(start_line)
                elif line2 == end_line:
                    on = False
                if on and not line2.startswith('# DOC:') and not line2.endswith('# DOC: skip'):
                    lines.append(str(lineno))
                lineno += 1
        if len(lines) == 0:
            raise RuntimeError('No start found')
        self.options['lines'] = ','.join(lines)
        if not 'language' in self.options:
            self.options['language'] = 'python'
        if dedent != 0:
            self.options['dedent'] = dedent
        return super().run()


def setup(app: 'Sphinx') -> Dict[str, Any]:
    directives.register_directive('smartinclude', SmartInclude)

    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True
    }