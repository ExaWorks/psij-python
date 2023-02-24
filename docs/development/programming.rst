Architecture
============

This section outlines the architecture of the Python PSI/J implementation for
those who want to contribute improvements to the core
components or write a new :class:`~psij.job_executor.JobExecutor` or
:class:`~psij.job_launcher.Launcher`. The information contained here is in
addition to the
`PSI/J Specification <https://exaworks.org/job-api-spec/specification>`_,
which should be read first.

The PSI/J specification splits implementations into two main parts:

    - The core classes, containing scheduler-agnostic code. Client code, wanting
      to maintain portability, should only directly reference the core classes.
    - Executors and launchers, which are specific to scheduler implementations
      and can be used interchangeably, provided that the underlying scheduler or
      launcher implementation exists.

Nearly all of the core classes described in the PSI/J Specification are simple
property containers and the behavior of the few exceptions is thoroughly
documented therein. There are, however, a few areas that are specific to the
current PSI/J Python implementation which are mostly a matter of implementation
and are not documented by the specification. These are:

    - The dynamic executor/launcher loading system.
    - The
      :class:`~psij.executors.batch.batch_scheduler_executor.BatchSchedulerExecutor`,
      an abstract submit-script based LRM executor class, which is a convenient superclass for executors interfacing with typical job schedulers.
    - The abstract script-based launcher, which is a base class for
      launchers that can be conveniently implemented by writing a bash script.

The Executor Loading System
---------------------------

The aim of the executor/launcher loading system is to allow side-loading of
executor and launcher implementations that are not bundled with the core PSI/J
Python distribution. Additionally, at least in theory, multiple versions of
an implementation for an executor or loader targeting the same underlying
scheduler implementation should be allowed. The goal is that, while compute
clusters may provide default installations of executors or launchers, the user
should have the ability to install and use custom versions of such launchers or
executors, even possibly for the same underlying schedulers. A secondary goal
is that the steps required to use a certain executor or launcher implementation
should be minimal. Specifically, installing the Python package containing such
an implementation should be enough to enable client code to discover and use
that implementation. However, the requirement that users be able to install
newer versions of a system-provided package means that a special mechanism
should exist, a mechanism able to refer to classes that exist in the same
nominal Python package, but in different directories on disk. Since Python does
not readily allow that, PSI/J implements a custom solution.

The solution chosen in the current PSI/J implementation is based on *descriptor
files* and Python `Namespace Packages <https://peps.python.org/pep-0420/>`_.
Specifically, when the main `psij` package is imported, code in
`psij/__init__.py` goes sequentially through elements in `PYTHONPATH` and
attempts to load all `.py` files in the `psij-descriptors` package. The
`psij-descriptors` package must be a namespace package. That is, it must not
contain an `__init__.py` file.

Files loaded from `psij-descriptors` (the descriptor files) are then
interpreted and expected to declare one or both of `__PSI_J_EXECUTORS__` or
`__PSI_J_LAUNCHERS__` as global variables, which are lists containing one or
more instances of [Descriptor](#descriptor). The code then iterates over all
such instances and calls `psij._plugins._register_plugin()`. The
`_register_plugin` method attempts to import the class pointed to by the `cls`
property of the descriptor, which is a string representing a fully qualified
class name. The loading is restricted to the `PYTHONPATH` entry in which the
descriptor was found. That is, if a descriptor is loaded from `~/lib/python`
and that descriptor has `cls='psij.executors.pbs.PBSExecutor'` then the file
`~/lib/python/psij/executors/pbs.py` must contain a class named `PBSExecutor`.
The absence of such a file or class will result in PSI/J being unable to
register the executor.

If an error occurs after a descriptor is loaded but before the actual executor
or launcher class is loaded, that error is stored. Successive attempts to
instantiate that executor/launcher using
:meth:`~psij.job_executor.JobExecutor.get_instance` or
:meth:`~psij.job_launcher.Launcher.get_instance` will result in the
stored exception being raised. This prevents packages with broken
implementations of executors or launchers from reporting errors unless there
is an actual attempt to use them.


The Batch Scheduler Executor
----------------------------

For a more end-goal oriented view of this topic, please see the :doc:`tutorial
for adding an executor <tutorial_add_executor>`.

This is an abstract base class for submit-script based executors. It assumes
a Local Resource Manager (LRM) that allows job submission by pointing a
*submit* command (a tool accessible through a standard POSIX `exec()`) to a
file that contains all relevant job information. It also assumes that there
exist commands for cancelling the job and for querying for the status of one
or more jobs previously submitted.

The general workflow used by the batch scheduler executor to submit a job is as
follows:

    1. Generate a submit script in the *work directory*, which is obtained
    from the `config` object at executor initialization, and which defaults to
    `~/.psij/work/<executor.name>`, where `<executor.name>` is the value of
    the `name` of the implementing class. The submit script is generated using
    the
    :meth:`~psij.executors.batch.batch_scheduler_executor.BatchSchedulerExecutor.generate_submit_script`
    method of the implementing class.

    2. Execute the command returned by
    :meth:`~psij.executors.batch.batch_scheduler_executor.BatchSchedulerExecutor.get_submit_command` to
    pass the generated submit script to the LRM.

    3. Invoke
    :meth:`~psij.executors.batch.batch_scheduler_executor.BatchSchedulerExecutor.job_id_from_submit_output`
    to obtain the job's native ID from the output of the submit command executed
    in step (2).

    4. Register the job with the *status polling thread*.

In parallel, an independent thread, the *status polling thread*, periodically
queries the LRM for status updates for the submitted jobs using the following
sequence of steps for each of the jobs registered in step (4), above:

    1. Run the command returned by
    :meth:`~psij.executors.batch.batch_scheduler_executor.BatchSchedulerExecutor.get_status_command`.

    2. Parse the output of the status command, above, using
    :meth:`~psij.executors.batch.batch_scheduler_executor.BatchSchedulerExecutor.parse_status_output`,
    which returns a dictionary mapping LRM id strings to :class:`~psij.job_status.JobStatus` objects.

    3. Update the job status with the status object obtained in step (2).

    4. If the job state is final, the job is removed from the list of jobs
    managed by the status polling thread.


Script Based Launchers
----------------------

Launchers are classes that represent entities that, when invoked on the rank 0
node, start the relevant number of executable instances for a job on the
allocated compute nodes. Script based launchers are simple wrappers around
scheduler-provided or general launcher tools, such as `mpirun`, `srun`, etc.
Currently, all PSI/J launchers are implemented as scripts and have
:class:`~psij.launchers.script_based_launcher.ScriptBasedLauncher` as a base
class.

The PSI/J executors leave the job of input and output redirection to the
launchers. Consequently, launcher scripts also take care of redirecting the
standard streams of the actual launcher tool, which is assumed to properly
aggregate the output streams of the job ranks.

In addition to the functions above, PSI/J launchers also take care of invoking
the pre- and post-launch scripts.

Since script based launchers are interchangeable, they must have a well
defined interface. This interface consists of:

    * The command line arguments, which are, in order:

        * The PSI/J job ID
        * A path to a log file that the launcher script can write debugging
          information to
        * The path of the pre-launch script/executable
        * The path of the post-launch script/executable
        * The path to the job `STDIN` file (or `/dev/null`)
        * The path to the job `STDOUT` file (or `/dev/null`)
        * The path to the job `STDERR` file (or `/dev/null`)

    * The output of the launcher script; this must either be terminated
      by the string `_PSI_J_LAUNCHER_DONE` as the last line or an error message
      that can help troubleshoot launching problems, such as errors from the
      underlying launcher executable.

Writing a custom script based launcher can be as easy as subclassing
:class:`~psij.launchers.script_based_launcher.ScriptBasedLauncher` and passing
a launcher script path to the base class constructor. For example, see the
`MPI launcher class <https://github.com/ExaWorks/psij-python/blob/main/src/psij/launchers/mpirun.py>`_ and the
`MPI launcher script <https://github.com/ExaWorks/psij-python/blob/main/src/psij/launchers/scripts/mpi_launch.sh>`_.
