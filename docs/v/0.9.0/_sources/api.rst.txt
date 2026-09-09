The PSI/J API
=============

The most important classes in this library are ``Job`` and ``JobExecutor``,
followed by ``Launcher``.

The Job Class and Its Modifiers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Job-related classes listed in this section (``Job``, ``JobSpec``,
``ResourceSpec``, and ``JobAttributes``) are independent of
executor implementations. The authors strongly recommend that users
program against these classes rather than adding executor-specific
configuration options, to the extent possible.

.. autoclass:: psij.Job
    :members:
    :noindex:

.. autoclass:: psij.JobStatus
    :members:
    :noindex:

.. autoclass:: psij.JobState
    :members:
    :noindex:

Job Modifiers
^^^^^^^^^^^^^

There can be a lot of configuration information that goes into each
resource manager job. Its walltime, partition/queue, the number of nodes
it needs, what kind of nodes, what quality of service the job requires, and
so on.

PSI/J splits those attributes into three groups: one for generic
POSIX information, one for resource information, and one for resource manager
scheduling policies.

.. autoclass:: psij.JobSpec
    :members:
    :noindex:

.. autoclass:: psij.ResourceSpec
    :members:
    :noindex:

.. autoclass:: psij.JobAttributes
    :members:
    :noindex:


.. _executors:

Executors
~~~~~~~~~

Executors are concrete implementations of mechanisms that execute jobs.
To get an instance of a specific executor, call
:meth:`JobExecutor.get_instance(name) <psij.job_executor.JobExecutor.get_instance>`,
with ``name`` being one of the installed executor names. Alternatively, directly
instantiate the executor, e.g.:

.. code-block:: python

    from psij.executors.flux import FluxJobExecutor

    ex = FluxJobExecutor()

Rather than:

.. code-block:: python

    import psij

    ex = psij.JobExecutor.get_instance('flux')

Executors can be
installed from multiple sources, so the precise list of executors
available to a specific installation of the PSI/J Python library can vary.
In order to get a list of available executors, you can run, in a
terminal:

.. code-block:: shell

    $ python -m psij plugins


JobExecutor Base Class
^^^^^^^^^^^^^^^^^^^^^^

The ``psij.JobExecutor`` class is abstract, but offers concrete static methods
for registering, fetching, and listing subclasses of itself.

.. autoclass:: psij.job_executor.JobExecutor
    :noindex:

The concrete executor implementations provided by this version of PSI/J Python
are:

Cobalt
^^^^^^

.. autoclass:: psij.executors.batch.cobalt.CobaltJobExecutor
    :noindex:

Flux
^^^^

.. autoclass:: psij.executors.flux.FluxJobExecutor
    :noindex:

LSF
^^^

.. autoclass:: psij.executors.batch.lsf.LsfJobExecutor
    :noindex:

PBS
^^^

.. autoclass:: psij.executors.batch.pbspro.PBSProJobExecutor
    :noindex:

Slurm
^^^^^

.. autoclass:: psij.executors.batch.slurm.SlurmJobExecutor
    :noindex:

Local
^^^^^

.. autoclass:: psij.executors.local.LocalJobExecutor
    :noindex:

Radical Pilot
^^^^^^^^^^^^^

.. autoclass:: psij.executors.rp.RPJobExecutor
    :noindex:

.. _launchers:


Launchers
~~~~~~~~~

Launchers are mechanisms to start the actual jobs on batch schedulers
once a set of nodes has been allocated for the job. In essence, launchers
are wrappers around the job executable which can provide additional
features, such as setting up an MPI environment, starting a copy of the
job executable on each allocated node, etc. To get a launcher instance,
call :meth:`Launcher.get_instance(name) <psij.launcher.Launcher.get_instance>`
with ``name`` being the name of a launcher. Like job executors,
launchers are plugins and can come from various places. To obtain a list
of launchers, you can run:

.. code-block:: shell

    $ python -m psij plugins

Launcher Base Class
^^^^^^^^^^^^^^^^^^^

Like the executor, the ``Launcher`` base class is abstract, but offers
concrete static methods for registering and fetching subclasses of itself.

.. autoclass:: psij.Launcher
    :noindex:

The PSI/J Python library comes with a core set of launchers, which are:

aprun
^^^^^

.. autoclass:: psij.launchers.aprun.AprunLauncher
    :members:
    :noindex:

jsrun
^^^^^

.. autoclass:: psij.launchers.jsrun.JsrunLauncher
    :members:
    :noindex:

srun
^^^^

.. autoclass:: psij.launchers.srun.SrunLauncher
    :members:
    :noindex:

mpirun
^^^^^^

.. autoclass:: psij.launchers.mpirun.MPILauncher
    :members:
    :noindex:

single
^^^^^^

.. autoclass:: psij.launchers.single.SingleLauncher
    :members:
    :noindex:

multiple
^^^^^^^^

.. autoclass:: psij.launchers.multiple.MultipleLauncher
    :members:
    :noindex:

Other Package Contents
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: psij.exceptions
    :members:
    :noindex:


API Reference
~~~~~~~~~~~~~

.. toctree::

    .generated/modules
