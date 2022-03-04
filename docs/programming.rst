The PSI/J API
=============


The PSI/J core
~~~~~~~~~~~~~~

The core API contains the central components of PSI/J. The core API classes are independent of executor implementations. User code should only program against the core API. The major classes are:

:class:`~psij.job.Job`
    Represents a scheduler job, including all its details and state.

:class:`~psij.job_spec.JobSpec`
    Contains the static description of a job at a level that would be supported by the POSIX interface, such as path to the executable, arguments, etc.

:class:`~psij.resource_spec.ResourceSpec`

    Describes resource requirements for the job, such as number of nodes, etc.

:class:`~psij.job_attributes.JobAttributes`
    Contains information about a job that goes beyond POSIX and is specific to batch schedulers, such as a queue name, walltime limit, etc.

:class:`~psij.job_state.JobState`
    An enumeration containing all possible states of a job.

:class:`~psij.job_status.JobStatus`
    An object that represents the transition of a job to a new :class:`~psij.job_state.JobState`.

:class:`~psij.job_executor.JobExecutor`
    The base class for a concrete method of executing a job, such as Slurm, or PBS.

:class:`~psij.launcher.Launcher`
    A base class representing a method of actually launching a job once resources are allocated for it, such as `mpirun`, `srun`, etc.

:py:mod:`~psij.exceptions`
    A module that contanins exception classes for the PSI/J Python library.


.. _executors:

Executors
~~~~~~~~~

Executors are concrete implementations of mechanisms that execute jobs. To get an instance of a specific executor, call :meth:`JobExecutor.get_instance(name) <psij.job_executor.JobExecutor.get_instance>`, with ``name`` being one of the installed executor names. Executors can be installed from multiple sources, so the precise list of executors avaiable to a specific installation of the PSI/J Python library can vary. In order to get a list of available executors, you can run, in a terminal:

.. code-block:: shell

    $ python -m psij plugins


The executor implementations provided by this version of PSI/J Python are:

:class:`cobalt <psij.executors.batch.cobalt.CobaltJobExecutor>`
    A job executor that can interact with the `Cobalt HPC Job Scheduler <https://xgitlab.cels.anl.gov/aig-public/cobalt>`_, which is used by `Argonne's <www.anl.gov>`_ `ALCF <www.alcf.anl.gov>`_ systems.

:class:`flux <psij.executors.flux.FluxJobExecutor>`
    Job executor for the `Flux scheduler <http://flux-framework.org/>`_.

:class:`local <psij.executors.local.LocalJobExecutor>`
    A job executor that runs jobs locally by forking a subprocess.

:class:`lsf <psij.executors.batch.lsf.LsfJobExecutor>`
    An implementation of a job executor for the `IBM Spectrum LSF workload manager <https://www.ibm.com/docs/en/spectrum-lsf>`_.

:class:`rp <psij.executors.rp.RPJobExecutor>`
    Job executor for the `RADICAL Pilot system <https://radical-cybertools.github.io/radical-pilot/>`_.

:class:`saga <psij.executors.saga.SagaExecutor>`
    An executor that delegates job execution to the `RADICAL-SAGA <https://radical-cybertools.github.io/saga-python/index.html>`_ library.

:class:`slurm <psij.executors.batch.slurm.SlurmJobExecutor>`
    An executor for the `Slurm Workload Manager <https://slurm.schedmd.com/overview.html>`_.


.. _launchers:

Launchers
~~~~~~~~~

Launchers are mechanisms to start the actual jobs on batch schedulers once a set of nodes has been allocated for the job. In essence, launchers are wrappers around the job executable which can provide additional features, such as setting up an MPI environment, starting a copy of the job executable on each allocated node, etc. To get a launcher instance, call :meth:`Launcher.get_instance(name) <psij.launcher.Launcher.get_instance>` with ``name`` being the name of a launcher. Like job executors, above, launchers are plugins and can come from various places. To obtain a list of launchers, you can run:

.. code-block:: shell

    $ python -m psij plugins

The PSI/J Python library comes with a core set of launchers, which are:

:class:`aprun <psij.launchers.aprun.AprunLauncher>`
    Launches jobs using `Cobalt's <https://xgitlab.cels.anl.gov/aig-public/cobalt>`_ ``aprun``.

:class:`jsrun <psij.launchers.jsrun.JsrunLauncher>`
    Starts jobs using ``jsrun`` provided by the `IBM Spectrum LSF workload manager <https://www.ibm.com/docs/en/spectrum-lsf>`_.

:class:`mpirun <psij.launchers.mpirun.MPILauncher>`
    Launches jobs using ``mpirun``, which is a tool provided by `MPI <https://www.mpi-forum.org/>`_ implementations, such as `Open MPI <https://www.open-mpi.org/>`_.

:class:`multiple <psij.launchers.multiple.MultipleLauncher>`
    Starts multiple identical instances of the same process on the same machine.

:class:`single <psij.launchers.single.SingleLauncher>`
    Starts a single instance of the job executable locally. This is the default launcher, which is used if nothing is explicitly specified.

:class:`srun <psij.launchers.srun.SrunLauncher>`
    Starts job using ``srun``, which is part of the `Slurm Workload Manager <https://slurm.schedmd.com/overview.html>`_.


API Reference
~~~~~~~~~~~~~

.. toctree::

    .generated/modules
