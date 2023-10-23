import pathlib
from abc import ABC
from typing import Dict, Callable, IO

import pystache

from psij import Job, JobExecutorConfig
from .escape_functions import bash_escape


class SubmitScriptGenerator(ABC):
    """A base class representing a submit script generator.

    A submit script generator is used to render a :class:`~psij.Job` (together with all its
    properties, including :class:`~psij.JobSpec`, :class:`~psij.ResourceSpec`, etc.) into a submit
    script specific to a certain batch scheduler.
    """

    def __init__(self, config: JobExecutorConfig) -> None:
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

    def generate_submit_script(self, job: Job, context: Dict[str, object], out: IO[str]) -> None:
        """Generates a job submit script.

        Concerete implementations of submit script generators must implement this method. Its
        purpose is to generate the content of the submit script. For an extensive explanation of
        the mechanism behind this process, see :class:`~.BatchSchedulerExecutor`.

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
        pass


class TemplatedScriptGenerator(SubmitScriptGenerator):
    """A Mustache templates submit script generator.

    This script generator uses Pystache (https://pypi.org/project/pystache/), which is a Python
    implementation of the Mustache templating language (https://mustache.github.io/).
    """

    def __init__(self, config: JobExecutorConfig, template_path: pathlib.Path,
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
        with template_path.open('r') as template_file:
            self.template = pystache.parse(template_file.read())
        self.renderer = pystache.Renderer(escape=escape)

    def generate_submit_script(self, job: Job, context: Dict[str, object], out: IO[str]) -> None:
        """See :func:`~SubmitScriptGenerator.generate_submit_script`.

        Renders a submit script using the template specified when this generator was constructed.
        """
        out.write(self.renderer.render(self.template, context))
