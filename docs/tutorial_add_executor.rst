Adding an executor
==================

terminology questions: are these consistent with other docs and usage?

local resource manager - i'm pulling from globus toolkit 2 terminology here

allocation - other exaworks code talks about psi/j providing an interface for "obtaining allocations" -- but maybe this should be "running jobs" not "obtaining allocations" ?



What is an executor and why might you want to add one?
------------------------------------------------------

PSI/J provides a common interface for obtaining allocations on compute resources.

Usually, those compute resources will already have some system [local resource manager] in place (for example, SLURM) to manage allocations. PSI/J provides a common interface to those local resource managers.

A PSI/J executor is the code that tells the core of PSI/J how to interact with a local resource manager.

A PSI/J executor needs to implement the abstract methods defined on the :class:`psij.job_executor.JobExecutor` base class. The documentation for that class has reference material for each of the methods that won't be repeated here.

For many systems, the :class:`psij.executors.batch.BatchSchedulerExecutor` subclass provides further useful structure to help implement JobExecutor. This tutorial will focus on using BatchSchedulerExecutor as a base, rather than implementing JobExecutor directly.

The batch scheduler executor is based around a model where interactions with a local resource manager happen via command line invocations. For example, with SLURM, commands are sbatch to submit a request for an allocation and squeue to discover allocation status.

To use BatchSchedulerExecutor for a new local resource manager that uses this command line interface, subclass BatchSchedulerExecutor and add in code that understands how form the comand lines necessary to submit a request for an allocation and to get allocation status.

Here's an example of doing that to add support for the PBS Pro local resource manager to PSI/J.

First setup a directory structure:

mkdir project/
cd project/
mkdir psijpbs
mkdir psij-descriptors

We're going to create three source files in this directory structure:

* ``psijpbs/pbspro.py`` - this will contain the bulk of the code

* ``psijpbs/pbspro.mustace`` - this will contain a template for what a PBS Pro submission should look like

* ``psij-descriptors/pbspro_descriptor.py`` - this file describes the PBS Pro provider to the PSI/J core, so that it can make it available to users

First, we'll build a skeleton that won't work, and see that it doesn't work in the test suite. Then we'll build up to the full functionality.

Assumptions:

* you have the psij python package installed already and are able to run whatever basic verification we think is necessary

* you are able to submit to PBS Pro on a local system (don't worry if you don't have this and are just following along to understand what's happening - just pretend...)

add the project directory to the python path directory:

export PYTHONPATH=$(pwd):$PYTHONPATH

create a simple BatchSchedulerExecutor subclass that does nothing, in `psijpbs/pbspro.py`:

from psij.executors.batch.batch_scheduler_executor import BatchSchedulerExecutor

class PBSProJobExecutor(BatchSchedulerExecutor):
    pass

and create a descriptor file to tell psi/j about this, ``psij-descriptors/pbspro.py``

from distutils.version import StrictVersion

from psij._descriptor import _Descriptor


__PSI_J_EXECUTORS__ = [_Descriptor(name='pbspro', version=StrictVersion('0.0.1'),
                                   cls='psijpbs.pbspro.PBSProJobExecutor')]

../tutorial-play/psij-descriptors/pbspro.py lines 1-8/8 (END)


Now, run the test suite - it should fail with an error reporting that the resource manager specific methods of BatchSchedulerExecutor have not been implemented:

PYTHONPATH=$PWD/src:../wheverever/project/ pytest 'tests/test_executor.py::test_simple_job' --executors=pbspro

NB for us: this is an ugly command line... `make test` doesn't quite do what I want... what's the best way?

TypeError: Can't instantiate abstract class PBSProJobExecutor with abstract methods generate_submit_script, get_cancel_command, get_status_command, get_submit_command, job_id_from_submit_output, parse_status_output, process_cancel_command_output

That error message tells us what we need to implement. There are three broad pieces of functionality:

* submitting a job:

generate_submit_script
get_submit_command
job_id_from_submit_output

* cancelling a job

get_cancel_command
process_cancel_command_output

* requesting job status

get_status_command
parse_status_output


Let's implement all of these with stubs that return NotImplementedError that we will then flesh out::

  class PBSProJobExecutor(BatchSchedulerExecutor):

   def generate_submit_script(*args, **kwargs):
        raise NotImplementedError

    def get_submit_command(*args, **kwargs):
        raise NotImplementedError

    def job_id_from_submit_output(*args, **kwargs):
        raise NotImplementedError

    def get_cancel_command(*args, **kwargs):
        raise NotImplementedError

    def process_cancel_command_output(*args, **kwargs):
        raise NotImplementedError

    def get_status_command(*args, **kwargs):
        raise NotImplementedError

    def parse_status_output(*args, **kwargs):
        raise NotImplementedError

Now running the same pytest command will give a different error - further along into attempting to submit a job:

... ::

  >       assert config
  E       AssertionError

which is something to do with configurations...

turns out this __init__ gets a bit upset with an optional config and maybe that will get fixed in the codebase.

But for now, if no config is supplied, we need to generate a config. For now, we're not going ot have a
PBS-specific configuration, so we'll just use the existing BatchJobExecutorConfig class.

Define a new __init__ method that will define a default configuration::

  from psij.executors.batch.batch_scheduler_executor import BatchSchedulerExecutorConfig

  ...

    def __init__(self, *, url, config):
        if config is None:
            config = BatchSchedulerExecutorConfig()
        super().__init__(url=url, config=config)


If we need to add in any PBS specific configuration options - this is where we're going to do it.

URL is a "very import, you can ignore" parameter. Ignore it.

Running pytest again, we get as far as seeing PSI/J is trying to do submit-related stuff::

    def generate_submit_script(*args, **kwargs):
 >       raise NotImplementedError
 E       NotImplementedError

 ../tutorial-play/psijpbs/pbspro.py:13: NotImplementedError

Implementing job submission
===========================

To implement submission, we need to implement three abstract methods, as listed earlier on:

* :py:meth:`psij.executors.batch.batch_scheduler_executor.BatchSchedulerExecutor.generate_submit_script`
* :py:meth:`psij.executors.batch.batch_scheduler_executor.BatchSchedulerExecutor.get_submit_command`
* :py:meth:`psij.executors.batch.batch_scheduler_executor.BatchSchedulerExecutor.job_id_from_submit_output`

You can read the docstrings for each of these methods for more information, but briefly the submission process is:

A submit script, of a format specific to the resource manager, is generated by ``generate_submit_script``.

That script is submitted to the resource manager by calling a command line. The command line is returned by ``get_submit_command``.

Then the output of that command is interpreted by ``job_id_from_submit_output`` to extract a job ID, which can be used later on when cancelling or getting job status.

So let's implement those.

In line with other PSI/J executors, we're going to delegate script generation to a template based helper. So add a line to initialise a :py:class:`TemplatedScriptGenerator` in the
executor initializer, pointing at a (as yet non-existent) template file, and replace ``generate_submit_script`` with a delegated call to `TemplatedScriptGenerator`::

    from pathlib import Path
    from psij import Job
    from typing import Dict, TextIO
    from psij.executors.batch.script_generator import TemplatedScriptGenerator


    class PBSProJobExecutor(BatchSchedulerExecutor): 

    ...

        def __init__(self, url: Optional[str] = None, config: Optional[PBSProExecutorConfig] = None):
            if not config:
                config = BatchSchedulerExecutorConfig()
            super().__init__(url=url, config=config)
            self.generator = TemplatedScriptGenerator(config, Path(__file__).parent / 'pbspro.mustache')

        def generate_submit_script(self, job: Job, context: Dict[str, object],
                                   submit_file: TextIO) -> None:
            self.generator.generate_submit_script(job, context, submit_file)


Now the test will fail with an error like this, because that template doesn't exist::

    E       FileNotFoundError: [Errno 2] No such file or directory: '/home/you/project/psijpbs/pbspro.mustache'


This file is very PBS specific - if you're writing for a different local resource manager, you'll have to adapt the template to work. There are several mustache templates in the psi/j source which you can look at for examples.

Here is a very simple template for PBS, lacking a lot of features. A full template should look at all of the fields in the supplied :py:class:`Job` object, as well as any executor-specific parameters supplied in the ``config`` parameter to ``__init__``.

TODO: put in a simple template that is enough to submit but without the many many fields.

Next, the test will fail because ``get_submit_command`` is missing. This method is going to give a command line to run to submit the tempate-generated submit file. In PBS, that submission happens by running a command like this::

    qsub myscript.sub

Here's an implementation of ``get_submit_command`` that will make a command like this::

    def get_submit_command(self, job: Job, submit_file_path: Path) -> List[str]:
        return ['qsub', str(submit_file_path.absolute())]


