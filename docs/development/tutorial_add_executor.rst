Adding an executor
==================

This tutorial will write an executor for PBSPro using the PSI/J batch scheduler
executor interface.

It should be useful when writing an executor for any HPC style scheduler
that looks like SLURM or PBSPro.


What Is an Executor and Why Might You Want to Add One?
------------------------------------------------------

PSI/J provides a common interface for obtaining allocations on compute resources. Usually, those compute resources will already have a batch scheduler in place (for example, SLURM).

A PSI/J executor is the code that tells the core of PSI/J how to interact with a batch scheduler so that it can provide a common interface to applications.

A PSI/J executor needs to implement the abstract methods defined on the :class:`psij.job_executor.JobExecutor` base class.
The documentation for that class has reference material for each of the methods that won't be repeated here.

For batch scheduler systems, the :class:`.BatchScheduler` subclass provides further useful structure to help with the implementation.
This tutorial will focus on using BatchScheduler as a base, rather than implementing JobExecutor directly.

The batch scheduler executor is based on a model where interactions with a local resource manager happen via command line invocations.
For example, with PBS `qsub` and `qstat` commands are used to submit a request and to see status.

To use BatchScheduler for a new local resource manager that uses this command line interface, subclass BatchScheduler and add in code that understands how to form the command lines necessary to submit a request for an allocation and to get allocation status. This tutorial will do that for PBSPro. Then use a simple subclass of
:class:`.BatchSchedulerExecutor` to point to the subclassed BatchScheduler.

PSI/J can have both async and synchronous (plain) versions of executors. A mechanism is provided for easily implementing both versions
of executors for batch scheduler systems without needing to write the relevant code twice.

Adding an Executor
------------------

First set up a directory structure:


.. code-block:: console

    mkdir project/
    cd project/
    mkdir psijpbs
    mkdir psij-descriptors


We're going to create three source files in this directory structure:

* ``psijpbs/pbspro.py`` - This will contain the bulk of the code.

* ``psijpbs/pbspro.mustache`` - This will contain a template for a PBS Pro job submission file.

* ``psij-descriptors/pbspro_descriptor.py`` - This file tells the PSI/J core what this package implements.

Next, we will create a virtual environment to handle dependencies:

.. code-block:: console

    python3 -m venv .venv
    source .venv/bin/activate

Prerequisites:

* You have the psij-python package installed and are able to run whatever basic verification you think is necessary. You can do so with the following command:

.. code-block:: console

    pip install psij-python

* You are able to submit to PBS Pro on a local system.

First, we'll build a skeleton that won't work, and see that it doesn't work in the test suite. Then we'll build up to the full functionality.

A Not-implemented Stub
----------------------

Add the project directory to the Python path directory:

.. code-block:: console

    export PYTHONPATH=$(pwd):$PYTHONPATH


Create a simple BatchScheduler subclass that does nothing new in `psijpbs/pbspro.py`:

.. code-block:: Python

    from psij.executors.batch.batch_scheduler_executor import SyncBatchSchedulerExecutor, \
        BatchScheduler, BatchSchedulerExecutorConfig, AsyncBatchSchedulerExecutor

    class PBSProBatchScheduler(BatchScheduler):
        pass

This class will contain the PBSPro specific code.

Now, in the same file, define the actual executor classes that will use the above ``BatchScheduler`` definition, one
synchronous and one async:

.. code-block:: Python

    from typing import Tuple, Type

    class PBSProJobExecutor(SyncBatchSchedulerExecutor):
        def _get_concrete_classes(self) \
                -> Tuple[Type[BatchScheduler], Type[BatchSchedulerExecutorConfig]]:
            return PBSProBatchScheduler, BatchSchedulerExecutorConfig


    class AsyncPBSProJobExecutor(AsyncBatchSchedulerExecutor):
        def _get_concrete_classes(self) \
                -> Tuple[Type[BatchScheduler], Type[BatchSchedulerExecutorConfig]]:
            return PBSProBatchScheduler, BatchSchedulerExecutorConfig


and create a descriptor file to tell PSI/J about this, ``psij-descriptors/pbspro_descriptor.py`` (the name
of the file is not relevant -- PSI/J will look for all files in the `psij-descriptors` package):

.. code-block:: Python

    from packaging.version import Version
    from psij.descriptor import Descriptor

    __PSI_J_EXECUTORS__ = [
        Descriptor(name='pbspro', version=Version('0.0.1'),
                   cls='psijpbs.pbspro.PBSProJobExecutor')
    ]


    __PSI_J_ASYNC_EXECUTORS__ = [
        Descriptor(name='pbspro', version=Version('0.0.1'),
                   cls='psijpbs.pbspro.AsyncPBSProJobExecutor')
    ]


Write a simple test to submit a simple job to the new executor in `psijpbs/test.py`:

.. code-block:: Python

    from psij import JobExecutor, Job, JobSpec

    ex = JobExecutor.get_instance('pbspro')
    job = Job(JobSpec('/bin/date'))

    ex.run(job)

Now, run the example. It should fail with an error reporting that the resource manager specific methods of BatchScheduler have not been implemented:

.. code-block:: console

  python psijpbs/test.py

  TypeError: Can't instantiate abstract class PBSProBatchScheduler without an implementation for abstract methods '__init__', 'generate_submit_script', 'get_cancel_command', 'get_list_command', 'get_status_command', 'get_submit_command', 'job_id_from_submit_output', 'parse_status_output', 'process_cancel_command_output'


That error message tells us what we need to implement. There are four broad pieces of functionality:

* Submitting a job::

    generate_submit_script
    get_submit_command
    job_id_from_submit_output

* Requesting job status::

    get_status_command
    parse_status_output

* Cancelling a job::

    get_cancel_command
    process_cancel_command_output

* Listing jobs::

    get_list_command

as well as a constructor, which must be implemented with the correct signature so that our class
can be instantiated automatically.

Let's implement all of these with stubs that return a NotImplementedError that we will then flesh out:

.. code-block:: Python

    class PBSProBatchScheduler(BatchScheduler):

        def __init__(self, config: BatchSchedulerExecutorConfig) -> None:
            raise NotImplementedError

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

        def get_list_command(*args, **kwargs):
            raise NotImplementedError


Now running the same pytest command will give a different error further along into attempting to submit a job:

.. code-block:: console

    File "psijpbs/pbspro.py", line 8, in __init__
        raise NotImplementedError
    NotImplementedError

Our ``__init__`` method needs to be implemented. We provide a dummy implementation for now.

.. code-block:: Python

    def __init__(self, config: BatchSchedulerExecutorConfig) -> None:
        pass


Running pytest again, we get as far as seeing PSI/J is trying to do submit-related stuff:

.. code-block:: console

    File "psijpbs/pbspro.py", line 11, in generate_submit_script
        raise NotImplementedError
    NotImplementedError


Implementing Job Submission
---------------------------

To implement submission, we need to implement three methods:

* :py:meth:`psij.executors.batch.batch_scheduler_executor.BatchScheduler.generate_submit_script`
* :py:meth:`psij.executors.batch.batch_scheduler_executor.BatchScheduler.get_submit_command`
* :py:meth:`psij.executors.batch.batch_scheduler_executor.BatchScheduler.job_id_from_submit_output`

You can read the docstrings for each of these methods for more information, but briefly the submission process is:

1. ``generate_submit_script`` generates a submit script specific to the batch scheduler.

2. ``get_submit_command`` returns the command line necessary to submit that script to the batch scheduler.

The output of that command should be interpreted by ``job_id_from_submit_output`` to extract a batch scheduler specific job ID,
which can be used later when cancelling a job or getting job status.

In line with other PSI/J executors, we're going to delegate script generation to a template based helper. So add a line to initialize a :py:class:`.TemplatedScriptGenerator` in the
executor initializer, pointing at a (as yet non-existent) template file, and replace ``generate_submit_script`` with a delegated call to `TemplatedScriptGenerator`:

.. code-block:: Python

    from pathlib import Path
    from psij import BaseJob
    from typing import Dict, Iterable
    from psij.executors.batch.script_generator import TemplatedScriptGenerator


    class PBSProBatchScheduler(BatchScheduler):
    ...

        def __init__(self, config: BatchSchedulerExecutorConfig) -> None:
            self.generator = TemplatedScriptGenerator(config, Path(__file__).parent / 'pbspro.mustache')

        def generate_submit_script(self, job: BaseJob, context: Dict[str, object]) -> Iterable[str]:
            return self.generator.render(job, context)


Now the test will fail with an error like this, because that template doesn't exist:

.. code-block:: console

    E       FileNotFoundError: [Errno 2] No such file or directory: '...psijpbs/pbspro.mustache'


Here is a very simple template for PBS, lacking a lot of features. A full template should use all of the fields in the supplied :py:class:`psij.Job` object, as well as any executor-specific parameters supplied in the ``config`` parameter to ``__init__``:

.. code-block:: bash

  #!/bin/bash

  {{#job.name}}
  #PBS -N="{{.}}"
  {{/job.name}}

  {{#job.spec.inherit_environment}}
  #PBS -V
  {{/job.spec.inherit_environment}}

  {{#job.spec.attributes}}
    {{#duration}}
  #PBS -l walltime={{.}}
    {{/duration}}
    {{#custom_attributes.pbs}}
  #PBS --{{key}}="{{value}}"
    {{/custom_attributes.pbs}}

  {{/job.spec.attributes}}

  #PBS -e /dev/null
  #PBS -o /dev/null

  {{#job.spec.directory}}
  cd "{{.}}"
  {{/job.spec.directory}}

  exec &>> "{{psij.script_dir}}/$PBS_JOBID.out"

  {{#psij.launch_command}}{{.}} {{/psij.launch_command}}

  {{!we redirect to a file tied to the native ID so that we can reach the file with attach().}}
  echo "$?" > "{{psij.script_dir}}/$PBS_JOBID.ec"


Next, the test will fail because ``get_submit_command`` is missing. This method is going to give a command line to run to submit the tempate-generated submit file. In PBS, that submission happens by running a command like this:

.. code-block:: console

    > qsub c.submit
    2152.edtb-01.mcp.alcf.anl.gov


Here's an implementation of ``get_submit_command`` that will make such a command:

.. code-block:: Python

    from typing import List

    class PBSProBatchScheduler(BatchScheduler):
    ...
        def get_submit_command(self, job: BaseJob, submit_file_path: Path) -> List[str]:
            return ['qsub', str(submit_file_path.absolute())]

The implementation so far is enough to get jobs to run in PBS, but not enough for PSI/J to make sense of what it has submitted.

The final step in submission is implementing ``job_id_from_submit_output``. This interprets the output of the submit command to find the batch schedulers's job ID for the newly created job.

In the PBS Pro case, as shown in the example above, that is pretty straightforward. The entire output is the job ID:

.. code-block:: Python

    def job_id_from_submit_output(self, out: str) -> str:
        return out.strip()


That's enough to get jobs submitted using PSI/J, but not enough to run the test suite. Instead, the test suite will appear to hang, because the PSI/J core code gets a bit upset by status monitoring methods raising a NotImplementedError.


Implementing Status
-------------------

PSI/J needs to ask the batch scheduler for the status of jobs that it has submitted. This can be done with ``BatchScheduler`` by overriding these two methods, which we stubbed out as not-implemented earlier on:

* :py:meth:`.BatchScheduler.get_status_command` - Like ``get_submit_command``, this should return a batch scheduler-specific command line, this time to output job status.

* :py:meth:`.BatchScheduler.parse_status_output` - This will interpret the output of the above status command, a bit like ``job_id_from_submit_output``.

Here's an implementation for ``get_status_command``:

.. code-block:: Python

    from typing import Collection

    class PBSProBatchScheduler(BatchScheduler):
    ...
        def get_status_command(self, native_ids: Collection[str]) -> List[str]:
            ids = ','.join(native_ids)
            return ['qstat',  '-f', '-F', 'json', '-x'] + list(native_ids)

This constructs a command line which looks something like this:


.. code-block:: console

    qstat -f -F json -x 2154.edtb-01.mcp.alcf.anl.gov

The parameters change the default behavior of ``qstat`` to something more useful for parsing: ``-f`` asks for full output, with `-x` including information for completed jobs (which is normally suppressed) and ``-F json`` asking for the output to be formatted as JSON (rather than a default text tabular view).

This JSON output, which is passed to ``parse_status_output`` looks something like this (with a lot of detail removed):

.. code-block:: json

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

Here is an implementation for ``parse_status_output``, as well as a helper dictionary ``_STATE_MAP``:

.. code-block:: Python

    import json
    from psij import JobState, JobStatus
    from psij.executors.batch.batch_scheduler_executor import check_status_exit_code

    _STATE_MAP = {
        'Q': JobState.QUEUED,
        'R': JobState.ACTIVE,
        'F': JobState.COMPLETED
    }

    class PBSProBatchScheduler(BatchScheduler):
    ...

        def parse_status_output(self, exit_code: int, out: str) -> Dict[str, JobStatus]:
            check_status_exit_code('qstat', exit_code, out)
            r = {}

            report = json.loads(out)
            jobs = report['Jobs']
            for native_id in jobs:
                native_state = jobs[native_id]["job_state"]
                state = _STATE_MAP[native_state]

                msg = jobs[native_id]["comment"]
                r[native_id] = JobStatus(state, message=msg)

            return r

``parse_status_output`` is given both the stdout and the exit code of ``qstat`` and must either transcribe that into a dictionary of :py:class:`psij.JobStatus` objects describing the state of each job, or raise an exception.

This implementation uses a helper, :func:`psij.executors.batch.batch_scheduler_executor.check_status_exit_code`, which will raise an exception if ``qstat`` exited with a non-zero exit code. Then, it assumes that the ``qstat`` output is JSON and deserialises, and for each job in the JSON, it uses two fields to create a ``psij.JobStatus`` object: a human readable message is taken from the PBS ``comment`` field, and a machine readable status is converted from a single letter PBS status (such as F for finished, or Q for queued) into a PSI/J :py:class:`psij.JobState` via the ``_STATE_MAP`` dictionary.

With these status methods in place, the test script from before should execute to completion.

We still haven't implemented the cancel and list methods, though. We will do so in the next steps.


Implementing Cancel
-------------------

The two methods to implement for cancellation follow the same pattern as for submission and status:

* :py:meth:`.BatchScheduler.get_cancel_command` - This should form a command for cancelling a job.
* :py:meth:`.BatchScheduler.process_cancel_command_output` - This should interpret the output from the cancel command.

It looks like you don't actually need to implement `process_cancel_command_output` beyond the stub we already have, to make the abstract class mechanism happy. Maybe that's something that should change in psi/j?

Here's an implementation of `get_cancel_command`:

.. code-block:: Python

    def get_cancel_command(self, native_id: str) -> List[str]:
        return ['qdel', native_id]

That's enough to tell PBS Pro how to cancel a job, but it isn't enough for PSI/J to know that a job was actually cancelled: the JobState from `parse_status_output` will still return a state of COMPLETED, when we actually want CANCELED. That's because the existing job marks a job as COMPLETED whenever it reaches PBS Pro state `F`—no matter how the job finished.

So here's an updated `parse_status_output` which checks the ``Exit_status`` field in the qstat JSON to see if it exited with status code 265—that means that the job was killed with signal 9. and if so, marks the job as CANCELED instead of COMPLETED:

.. code-block:: Python

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

The ``process_cancel_command_output`` method is only called when the cancel command exits with a non-zero exit code. The simplest
and most likely implementation for it is to raise an error:

.. code-block:: Python

    def process_cancel_command_output(self, exit_code: int, out: str) -> None:
        raise SubmitException('Failed job cancel job: %s' % out)


Implementing List
-----------------

The :meth:`.JobExecutor.list` method is used to list all the jobs that the batch scheduler sees
for the current user. It requires the following methods to be implemented:

* :meth:`.BatchScheduler.get_list_command`
* :meth:`.BatchScheduler.parse_list_output`


Here are implementations of these methods:

.. code-block:: Python

    import os

    class PBSProBatchScheduler(BatchScheduler):
    ...
        def get_list_command(self) -> List[str]:
            return ['qstat', '-u', os.getlogin()]

        def parse_list_output(self, out: str) -> List[str]:
            return [s.split()[0].strip() for s in out.splitlines()[2:]]


What's Missing?
---------------

The biggest thing that was omitted was in the mustache template. A :py:class:`psij.Job` object contains lots of options which could be transcribed into the template (otherwise they will be ignored). Have a look at the docstrings for :class:`.JobSpec` and at other templates in the PSI/J source code for examples.

The ``_STATE_MAP`` given here is also not exhaustive: if PBS Pro qstat returns a different state for a job than what is in it, this will break. So make sure you deal with all the states of your batch scheduler, not just a few that seem obvious.

How to Distribute Your Executor
-------------------------------

If you want to share your executor with others:

1. You can make a Python package and distribute that as an add-on without needing to interact with the PSI/J project. This is the recommended way, since it will
allow you to easily maintain the code and manage its release independently of the main PSI/J code.

2. You can make a pull request against the PSI/J repo. This is not recommended since it complicates the maintenance of the PSI/J core.
