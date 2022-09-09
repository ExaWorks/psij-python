Quickstart
==========

The following quickstart guide demonstrates how to install and use PSI/J to submit, monitor, and cancel a job on one of four supported batch schedulers. 

Installation
------------

PSI/J can be installed via pip or from GitHub source.

Install from pip
^^^^^^^^^^^^^^^^

pip install  psi-j

Install from source
^^^^^^^^^^^^^^^^^^^

git clone https://github.com/ExaWorks/psi-j-python.git
cd psi-j-python
pip install .

Requirements
^^^^^^^^^^^^

Python 3.7+

Submitting a job
----------------

PSI/J supports a number of common batch schedulers, providing a common Python interface to users. Submitting a basic job requires specification of the program (e.g., binary, script) to execute, resources to provision (e.g., number of nodes), and site-specific attributes (e.g., queue and allocation name). 

Choose from the tabs below for a simple example showing how to submit a job for that scheduler.  


.. rst-class:: executor-type-selector

Local // Slurm // LSF // PBS // Cobalt

.. code-block:: python

    from psij import Job, JobExecutor, JobSpec, JobAttributes, ResourceSpecV1

    executor = JobExecutor.get_instance("<&executor-type>")

    job = Job(
        JobSpec(
            executable="/bin/date",
            resources=ResourceSpecV1(node_count=1),
            attributes=JobAttributes(
                queue_name="<QUEUE_NAME>", project_name="<ALLOCATION>"
            ),
        )
    )
    
    executor.submit(job)



Monitoring your job
-------------------

PSI/J provides an asynchronous interface via which job status can be monitored. Jobs transition through a well-defined state model from NEW, QUEUED, ACTIVE, COMPLETED (or FAILED or CANCELED).  Job status can be retrieved as follows. 

.. code-block:: python

    job.status() 


As a callback, you can also wait on the job to complete as follows. 

.. code-block:: python

    job.wait()


Canceling your job
------------------
If supported by the underlying job scheduler, PSI/J jobs can be canceled as follows. 

.. code-block:: python

    job.cancel()

