Getting Started
===============

Installation
------------

PSI/J can be installed via `pip <https://pypi.org/project/pip/>`_
or from source.

Requirements
^^^^^^^^^^^^

The only requirements are Python 3.7+ and pip, which almost always
comes with Python.

Install from pip
^^^^^^^^^^^^^^^^


.. code-block:: console

    pip install  psi-j

Install from source
^^^^^^^^^^^^^^^^^^^

.. code-block:: console

    git clone https://github.com/ExaWorks/psi-j-python.git
    cd psi-j-python
    pip install .



Overview
--------

In PSI/J's terminology, a :class:`Job <psij.job.Job>` represents an executable
plus a bunch of attributes.  Static job attributes such as resource requirements
are defined by the :class:`JobSpec <psij.job_spec.JobSpec>` at
creation. Dynamic job attributes such as the :class:`JobState
<psij.job_state.JobState>` are modified by :class:`JobExecutors
<psij.job_executor.JobExecutor>` as the :class:`Job <psij.job.Job>`
progresses through its lifecycle.

A :class:`JobExecutor <psij.job_executor.JobExecutor>` represents a specific
Resource Manager, e.g. Slurm, on which the Job is being executed.  Generally,
when jobs are submitted, they will be queued for a variable period of time,
depending on how busy the target machine is. Once the Job is started, its
executable is launched and runs to completion.

In PSI/J, a job is submitted by :meth:`JobExecutor.submit(Job)
<psij.job_executor.JobExecutor.submit>` which permanently binds the Job to that
executor and submits it to the underlying resource manager.


Basic Usage
-----------

The most basic way to use PSI/J looks something like the following:

#. Create a :class:`JobExecutor <psij.job_executor.JobExecutor>` instance.
#. Create a :class:`JobSpec <psij.job_spec.JobSpec>` object and populate
   it with information about your job.
#. Create a :class:`Job <psij.job.Job>` with that
   :class:`JobSpec <psij.job_spec.JobSpec>`.
#. Submit the :class:`Job <psij.job.Job>` instance to the
   :class:`JobExecutor <psij.job_executor.JobExecutor>`.

That's all there is to it! Assuming there are no errors, you should
see a new entry in your resource manager's queue. Choose from the tabs below
for a very simple example showing how to submit a job for that resource manager.


.. rst-class:: executor-type-selector selector-mode-tabs

Local // Slurm // LSF // PBS // Cobalt

.. code-block:: python

    from psij import Job, JobExecutor, JobSpec

    ex = JobExecutor.get_instance("<&executor-type>")
    job = Job(JobSpec(executable="/bin/date"))
    ex.submit(job)

The ``executable="/bin/date")`` part tells PSI/J that we want the job to run
the ``/bin/date`` command. Once that command has finished executing
(which should be almost as soon as the job starts, since ``date`` does very little work)
the resource manager will mark the job as complete, triggering PSI/J to do the same.


Examples
--------

Up-to-date and actively tested examples can be found
`here <https://github.com/ExaWorks/psi-j-python/blob/main/tests/test_doc_examples.py>`_.
Tests of resource-manager-specific and site-specific values
(such as accounts, queues/partitions, etc.) can be found in files
in the same directory but tend to buried under
layers of indirection in order to reduce code complexity.
