import pathlib
import re
from abc import ABC, abstractmethod
from enum import Enum
from functools import partial
from typing import Dict, Callable, IO, Optional, Iterable

import pystache
from pystache.parser import ParsedTemplate, NON_BLANK_RE, _PartialNode

from psij import JobExecutorConfig
from .escape_functions import bash_escape
from ...base_job import BaseJob


# We monkey-patch the render method of pystache to allow pre-parsed partials.
# Otherwise, partials that are virtually immutable are re-parsed on every render
def patched_render(self, engine, context):
    template = engine.resolve_partial(self.key)
    if isinstance(template, ParsedTemplate):
        return template.render(engine, context)
    else:
        # Indent before rendering.
        template = re.sub(NON_BLANK_RE, self.indent + r'\1', template)

        return engine.render(template, context)


_PartialNode.render = patched_render


def _load_partial(partials, prev, name):
    try:
        partial = partials[name]
        if isinstance(partial, ParsedTemplate):
            return partial
    except KeyError:
        pass
    return prev(name)

class _Renderer(pystache.Renderer):  # type: ignore
    def str_coerce(self, val: object) -> str:
        if isinstance(val, Enum):
            return str(val.value)
        elif isinstance(val, bool):
            return str(int(val))
        else:
            return super().str_coerce(val)  # type: ignore

    def _make_load_partial(self):
        return partial(_load_partial, self.partials, super()._make_load_partial())


class SubmitScriptGenerator(ABC):
    """A base class representing a submit script generator.

    A submit script generator is used to render a :class:`~psij.Job` (together with all its
    properties, including :class:`~psij.JobSpec`, :class:`~psij.ResourceSpec`, etc.) into a submit
    script specific to a certain batch scheduler.
    """

    def __init__(self, config: Optional[JobExecutorConfig]) -> None:
        """
        Parameters
        ----------
        config
            An executor configuration containing configuration properties for the executor that
            is attempting to use this generator. Submit script generators are meant to work in
            close cooperation with batch scheduler job executors, hence the sharing of a
            configuration mechanism.
        """
        self.config = config

    def generate_submit_script(self, job: BaseJob,
                               context: Dict[str, object], out: IO[str]) -> None:
        """Generates a job submit script.

        Concrete implementations of submit script generators must implement this method. Its
        purpose is to generate the content of the submit script. For an extensive explanation of
        the mechanism behind this process, see :class:`~.BatchSchedulerExecutor`.

        .. deprecated:: 0.9.12
           This method is incompatible with various asyncio file libraries. Use
           :func:`render` instead.

        Parameters
        ----------
        job
            The job for which the submit script is to be generated.
        context
            A dictionary containing information about the context in which the job is being
            submitted. For details, see :class:`~.BatchSchedulerExecutor`.
        out
            An opened file-like object to which the contents of the submit script should be
            written.
        """
        for chunk in self.render(job, context):
            out.write(chunk)

    @abstractmethod
    def render(self, job: BaseJob, context: Dict[str, object]) -> Iterable[str]:
        """
        Renders a submit script as a collection of strings.

        Concrete implementations of submit script generators must implement this method. Its
        purpose is to generate the content of the submit script. For an extensive explanation of
        the mechanism behind this process, see :class:`~.BatchSchedulerExecutor`. The submit
        script is returned as an iterable that produces strings which are written consecutively
        to a file.

        Parameters
        ----------
        job
            The job for which the submit script is to be generated.
        context
            A dictionary containing information about the context in which the job is being
            submitted. For details, see :class:`~.BatchSchedulerExecutor`.

        Returns
        -------
        An iterable with the contents of the submit script split in one or more consecutive
        chunks.

        """
        pass


class TemplatedScriptGenerator(SubmitScriptGenerator):
    """A Mustache templates submit script generator.

    This script generator uses Pystache (https://pypi.org/project/pystache/), which is a Python
    implementation of the Mustache templating language (https://mustache.github.io/).
    """

    def __init__(self, config: Optional[JobExecutorConfig], template_path: pathlib.Path,
                 escape: Callable[[object], str] = bash_escape) -> None:
        """
        Parameters
        ----------
        config
            A configuration, which is passed to the base class.
        template_path
            The path to a Mustache template.
        escape
            An escape function to use for escaping values. By default, a function that escapes
            strings for use in bash scripts is used.
        """
        super().__init__(config)
        self.template = self._read_template(template_path)
        common_dir = pathlib.Path(__file__).parent / 'common'
        partials = {}

        for partial in ['batch_lib', 'stagein', 'stageout', 'cleanup']:
            partials[partial] = self._read_template(common_dir / f'{partial}.mustache')

        self.renderer = _Renderer(escape=escape, partials=partials,
                                  search_dirs=[str(common_dir)])

    def _read_template(self, path: pathlib.Path) -> ParsedTemplate:
        with path.open('r') as template_file:
            return pystache.parse(template_file.read())

    def render(self, job: BaseJob, context: Dict[str, object]) -> Iterable[str]:
        """See :func:`~SubmitScriptGenerator.render`.

        Renders a submit script using the template specified when this generator was constructed.
        """
        return [self.renderer.render(self.template, context)]
