Adding an executor
==================

Hello and welcome to my draft of a "write a batch executor" tutorial.

This text is written in part as a structure for a tutorial, and in part as commentary on what is awkward in psi/j from my user-programmer perspective. Part of tidying the text involves changing PSI/J to make this text nicer, rather than this document being purely *descriptive* of the psi/j core code.


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

* requesting job status

get_status_command
parse_status_output

* cancelling a job

get_cancel_command
process_cancel_command_output



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

    > qsub c.submit
    2152.edtb-01.mcp.alcf.anl.gov


Here's an implementation of ``get_submit_command`` that will make a command like this::

    from typing import List


    def get_submit_command(self, job: Job, submit_file_path: Path) -> List[str]:
        return ['qsub', str(submit_file_path.absolute())]

The implementation so far is enough to get jobs to run in PBS, but not enough for PSI/J to make sense of what it has submitted.

The final step in submission is implementing ``job_id_from_submit_output``. This interprets the output of the submit command to find the local resource manager's job ID for the newly created job.

In the PBS Pro case, as shown in the example above, that is pretty straightforward: the entire output is the job ID::

    def job_id_from_submit_output(self, out: str) -> str:
        return out.strip()


That's enough to get jobs submitted using PSI/J, but not enough to run the test - instead it will appear to hang, because the PSI/J core code gets a bit upset by status monitoring methods raising NotImplementedError.

Implementing status
===================

PSI/J needs to ask the local resource manager for status about jobs that it has submitted. This can be done with ``BatchSchedulerExecutor`` by overriding these two methods, which we stubbed out as not-implemented earlier on:

* :py:meth:`get_status_command` - like ``get_submit_command``, this will return a local resource manager specific commandline, this time to output job status.

* :py:meth:`parse_status_output` - this will interpret the output of the above status command, a bit like ``job_id_from_submit_output``.

Here's an implementation for ``get_status_command``::

    from typing import Collection

    def get_status_command(self, native_ids: Collection[str]) -> List[str]:
        ids = ','.join(native_ids)
        return ['qstat',  '-f', '-F', 'json', '-x'] + list(native_ids)

This constructs a command line which looks something like this::

    qstat -f -F json -x 2154.edtb-01.mcp.alcf.anl.gov

The parameters change the default behaviour of ``qstat`` to something more useful for parsing: ``-f`` asks for full output, with `-x` including information for completed jobs (which is normally suppressed) and ``-F json`` asking for the output to be formatted as JSON (rather than a default text tabular view).

This JSON output, which is passed to ``parse_status_output`` looks something like this (with a lot of detail removed)::

 {
    "pbs_version":"2022.0.0.20211103141832",
    "Jobs":{
        "2154.edtb-01.mcp.alcf.anl.gov":{
            "job_state":"F",
            "comment":"Job run at Mon Jan 24 at 08:39 on (edtb-01[0]:ncpus=1) and finished",
            "Exit_status":0,
        }
    }
 }

Here is an implementation for ``parse_status_output``, as well as a helper dictionary ``_STATE_MAP``::

    import json
    from psij import JobState, JobStatus
    from psij.executors.batch.batch_scheduler_executor import check_status_exit_code

    _STATE_MAP = {
        'Q': JobState.QUEUED,
        'R': JobState.ACTIVE,
        'F': JobState.COMPLETED
    }

    class PBSProJobExecutor: ...

        def parse_status_output(self, exit_code: int, out: str) -> Dict[str, JobStatus]:
            check_status_exit_code(_QSTAT_COMMAND, exit_code, out)
            r = {}

            report = json.loads(out)
            jobs = report['Jobs']
            for native_id in jobs:
                native_state = jobs[native_id]["job_state"]
                state = _STATE_MAP(native_state)

                msg = jobs[native_id]["comment"]
                r[native_id] = JobStatus(state, message=msg)

            return r

``parse_status_output`` is given both the stdout and the exit code of ``qstat`` and must either transcribe that into a dictionary of :py:class:`JobStatus` objects describing the state of each job, or raise an exception.

This implementation uses a helper, :py:meth:`check_status_exit_code`, which will raise an exception if ``qstat`` exited with a non-zero exit code. Then, it assumes that the ``qstat`` output is JSON and deserialises, and for each job in the JSON, it uses two fields to create a ``JobStatus`` object: a human readable message is taken from the PBS ``comment`` field, and a machine readable status is converted from a single letter PBS status (such as F for finished, or Q for queued) into a PSI/J :py:class:`JobState` via the ``_STATE_MAP`` dictionary.

With these status methods in place, the ``pytest`` command from before should execute to completion.

We still haven't implemented the cancel methods, though. That will be reveal by running a broader range of tests::

    PYTHONPATH=$PWD/src:$PYTHONPATH pytest 'tests' --executors=pbspro

which should give this error (amongst others -- this commandline formation is ugly and I'd like it to work more along the lines of `make test`)::

    FAILED tests/test_executor.py::test_cancel[pbspro] - NotImplementedError

Implementing cancel
===================

The two methods to implement for cancellation follow the same pattern as for submission and status:

* :py:meth:`get_cancel_command` - this should form a command for cancelling a job.
* :py:meth:`process_cancel_command_output` - this should interpret the output from the cancel command.

It looks like you don't actually need to implement process_cancel_command_output beyond the stub we already have, to make the abstract class mechanism happy. Maybe that's something that should change in psi/j?

Here's an implementation of `get_cancel_command`::

    def get_cancel_command(self, native_id: str) -> List[str]:
        return ['qdel', native_id]

That's enough to tell PBS Pro how to cancel a job, but it isn't enough for PSI/J to know that a job was actually cancelled: the JobState from `parse_status_output` will still return a state of COMPLETED, when we actually want CANCELED. That's because the existing job marks a job as COMPLETED whenever it reaches PBS Pro state `F` - no matter how the job finished.

So here's an updated `parse_status_output` which checks the ``Exit_status`` field in the qstat JSON to see if it exited with status code 265 - that means that the job was killed with signal 9. and if so, marks the job as CANCELED instead of completed::

    def parse_status_output(self, exit_code: int, out: str) -> Dict[str, JobStatus]:
        check_status_exit_code('qstat', exit_code, out)
        r = {}

        report = json.loads(out)
        jobs = report['Jobs']

        for native_id in jobs:
            job_report = jobs[native_id]
            native_state = job_report["job_state"]
            state = _STATE_MAP[native_state]

            if state == JobState.COMPLETED:
                if 'Exit_status' in job_report and job_report['Exit_status'] == 265:
                    state = JobState.CANCELED

            msg = job_report["comment"]
            r[native_id] = JobStatus(state, message=msg)

        return r


This isn't necessarily the right thing to do: some PBS installs will use 128+9 = 137 to represent this instead of 256 + 9 = 265, according to the PBS documentation.



What's missing?
===============

The biggest thing that was omitted was in the mustache template. A :py:class:`Job` object contains lots of options which could be transcribed into the template (otherwise they will be ignored). Have a look at the docstrings for ``Job`` and at other templates in the PSI/J source code for examples. (maybe a job spec URL reference here too?)

The _STATE_MAP given here is also not exhaustive: if PBS Pro qstat returns job in a different state, this will break. So make sure you deal with all the states of your local resource manager, not just a few that seem obvious.

The test suite doesn't seem to contain a test for jobs failing in a particular way with broken PBS: they should go into FAILED state, not COMPLETED state, with some similar check to the CANCELED state check. Probably the test suite should get a test for that - I've hit this problem elsewhere, when jobs don't run enough to make a ``.ec`` file (because PBS was locally broken). I'm not sure how to test that as it's a bit pbs specific?

How to distribute your executor
===============================

If you want to share your executor with others, here are two ways:

i) you can make a python package and distribute that as an add-on without needing to interact with the psi/j project

ii) you can make a pull request against the psi/j repo - link to contributing text file?

