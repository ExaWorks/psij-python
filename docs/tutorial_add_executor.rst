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

The bulk of the what needs to happen goes in ``pbspro.py``.

``pbspro.py`` should contain a subclass of BatchSchedulerExecutor, with methods defined to implement the following three activities:

* submitting a job

* cancelling a job

* requesting job status

