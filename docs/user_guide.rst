
User Guide
==========

PSI/J is a Python library for submitting and managing HPC jobs via arbitrary
Resource Managers (RMs). PSI/J abstracts the specific RM, making your code
RM-independent and portable. Currently, PSI/J supports the following RMs: Slurm,
LSF, Flux, Cobalt, PBS and local Linux OS.


Terminology
-----------

In PSI/J’s terminology, a :class:`Job <psij.job.Job>` represents an executable
plus its attributes.  Static job attributes such es resource requiremens are
defined by the :class:`JobSpec <psij.job_spec.JobSpec>` at creation, dynamic job
attributes such as the :class:`JobState <psij.job_state.JobState>` are updated
by PSI/J at runtime.

A :class:`JobExecutor <psij.job_executor.JobExecutor>` represents
a specific RM, e.g. Slurm, on which the Job is being executed.  Generally, when
jobs are submitted, they will be queued for a variable period of time, depending
on how busy the target machine is. Once the Job is started, its executable is
launched and runs to completion.

In PSI/J, a job is submitted by binding a Job object to a JobExecutor object
with an appropriate configuration. For example, one Job instance bound to
a JobExecutor object might represent a job submitted to LSF on ORNL Frontier,
another a job submitted to Slurm on NERSC Perlmutter, another a job submitted to
a Flux instance that runs in the cloud, and so on.


What is a JobExecutor?
----------------------

`JobExecutor.submit` creates a new resource manager job and permanently binds
the Job to it. Alternatively, a Job can be bound to an existing resource manager
job by calling `JobExecutor.attach`, passing in a Job and the ID of the
underlying resource manager job.

.. image:: psij_arch.png

PSI/J currently provides executors for the following backends:

  - `local` : run jobs on localhost
  - `flux`  : `Flux Scheduling Framework <https://flux-framework.org/>`_
  - `slurm` : `Slurm Scheduling System <https://slurm.schedmd.com/>`_
  - `lsf`   : `IBM Spectrum LSF <https://www.ibm.com/docs/en/spectrum-lsf>`_
  - `pbspro`: `Altair's PBS-Professional <https://www.altair.com/pbs-professional>`_
  - `cobalt`: ALCF's Cobalt Job Scheduler

We encourage the contribution of executors for additional backends - please
reference the `developers documentation
<development/tutorial_add_executor.html>`_ for details.


Using a Job Executor
--------------------

The most basic way to use PSI/J looks something like the following:

1. Create a JobExecutor instance.
2. Create a JobSpec object and populate it with information about your job.
3. Create a Job with that JobSpec.
4. Submit the Job instance to the JobExecutor.

On a Slurm cluster, this code might look like:

.. rst-class:: executor-type-selector selector-mode-tabs

Slurm // Local // LSF // PBS // Cobalt

.. code-block:: python

    from psij import Job, JobExecutor, JobSpec

    ex = JobExecutor.get_instance("<&executor-type>")
    job = Job(JobSpec(executable='/bin/date'))
    ex.submit(job)

And by way of comparison, other backends can be selected with the tabs above.
Note that the only difference is the argument to the get_instance method.

The Job Executor implementation will translate all PSI/J API activities into the
respective backend commands and run them on the backend, while at the same time
monitoring the backend jobs for failure, completion or other state updates.

Assuming there are no errors, you should see a new entry in your resource
manager’s queue after running that example above.


Configuring your job
--------------------

In the example above, the `executable='/bin/date'` part tells PSI/J that we want
the job to run the `/bin/date` command. But there are other parts to the job
which can be configured:

- arguments for the job executable
- environment the job is running it
- destination for standard output and error streams
- resource requirements for the job's execution
- accounting details to be used

That information is encoded in the JobSpec which is used to create the Job
instance.


Job Arguments
^^^^^^^^^^^^^

The executable's command line arguments to be used for a job are specified as
a list of strings in the arguments attribute of the JobSpec class.  For example,
our previous `/bin/date` job could be changed to request UTC time formatting:

.. code-block:: python

    from psij import Job, JobExecutor, JobSpec

    ex = JobExecutor.get_instance('slurm')
    job = Job(JobSpec(executable='/bin/date', arguments=['-u']))
    ex.submit(job)

Note: JobSpec attributes can also be added incrementally:

.. code-block:: python

    from psij import JobSpec

    spec = JobSpec()
    spec.executable = '/bin/date'
    spec.arguments = ['-u']


Job Environment
^^^^^^^^^^^^^^^

The Job environment is provided a environment variables to the executing job
- the are the equivalent of `export FOO=bar` on the shell command line.  Those
environment variables are specified as a dictionary of string-type key/value
pairs:

.. code-block:: python

    from psij import JobSpec

    spec = JobSpec()
    spec.executable = '/bin/date'
    spec.environment = {'TZ': 'America/Los_Angeles'}

Environment variables specified this way will overwrite settings from yuor shell
initialization files (`~/.bashrc`), including from any modules loaded in the
default shell environment.


Job StdIO
^^^^^^^^^

Standard output and standard error streams of the job can be individually
redirected to files by setting the `stdout_path` and `stderr_path` attributes:

.. code-block:: python

    from psij import JobSpec

    spec = JobSpec()
    spec.executable = '/bin/date'
    spec.stdout_path = '/tmp/date.out'
    spec.stderr_path = '/tmp/date.err'

The job's standard input stream can also be redirected to read from a file, by
setting the `spec.stdin_path` attribute.


Job Resources
^^^^^^^^^^^^^

A job submitted to a cluster is allocated a specific set of resources to run on.
The amount and type of resources are defined by a resource specification
`psij.ResourceSpec` which becomes a part of the job specification.  The resource specification supports the following attributes:

  - `node_count`: allocate that number of compute nodes to the job.  All
    cpu-cores and gpu-cores on the allocated node can be exclusively used by the
    submitted job.
  - `processes_per_node`: on the allocated nodes, execute that given number of
    processes.
  - `process_count`: the total number of processes (ranks) to be started
  - `cpu_cores_per_process`: the number of cpu cores allocated to each launched
    process.  PSI/J uses the system definition of a cpu core which may refer to
    a physical cpu core or to a virtual cpu core, aka. hardware thread.
  - `gpu_cores_per_process`: the number of gpu cores allocated to each launched
    process.  The system definition of an gpu core is used, but usually refers
    to a full physical GPU.
  - `exclusive_node_use`: When this boolean flag is set to `True`, then PSI/J
    will ensure that no other jobs, neither of the same user nor of other users
    of the same system, will run on any of the compute nodes on which processes
    for this job are launched.

A resource specification does not need to define all available attributes. In
fact, an empty resource spec is valid as it refers to a single process being
launched on a single cpu core.

The user should also take care not to define contradictory statements.  For
example, the following specification cannot be enacted by PSI/J as the specified
node count contradicts the value of `process_count / processes_per_node`:

.. code-block:: python

    from psij import JobSpec, ResourceSpec

    spec = JobSpec()
    spec.executable = '/bin/stress'
    spec.resource_spec = ResourceSpec(node_count=2, processes_per_node=2,
            process_count=2)


Processes versus ranks
""""""""""""""""""""""

All processes of the job will share a single MPI communicator
(`MPI_COMM_WORLD`), independent of their placement, and the term `rank` (which
usually refers to an MPI rank) is thus equivalent.  However, jobs started with
a single process instance may, depending on the executor implementation, not get
an MPI communicator.

TODO: reference the launcher section


Other Job Attributes
^^^^^^^^^^^^^^^^^^^^

Monitoring your job
-------------------

Getting status
^^^^^^^^^^^^^^

In all the above examples, we have submitted jobs without checking on what
happened to them. Once that command has finished executing (which, for /bin/date
should be almost as soon as the job starts) the resource manager will mark the
job as complete, triggering PSI/J to do the same via the :class:`JobStatus
<psij.job_status.JobStatus>` attribute of the Job.

.. image:: states.png

To wait for a job to complete once it has been submitted, it suffices to call the wait method with no arguments:
from psij import Job, JobExecutor, JobSpec

.. code-block:: python

    from psij import Job, JobExecutor, JobSpec

    job = Job(JobSpec(executable='/bin/date'))
    ex.submit(job)
    job.wait()

The wait call will return once the job has reached a terminal state, which
almost always means that it finished or was cancelled.

To distinguish jobs that complete successfully from ones that fail or are
cancelled, fetch the status of the job after calling wait:

.. code-block:: python

    job.wait()
    print(str(job.status))


Status Callbacks
^^^^^^^^^^^^^^^^

Waiting for jobs to complete with wait is fine if you don’t mind blocking while
you wait for a single job to complete. However, if you want to wait on multiple
jobs without blocking, or you want to get updates when jobs start running, you
can attach a callback to a JobExecutor which will fire whenever any job
submitted to that executor changes status.

To wait on multiple jobs at once:

.. code-block:: python

    import time
    from psij import Job, JobExecutor, JobSpec

    count = 100

    def callback(job, status):
        global count

        if status.final:
            print(f"Job {job} completed with status {status}")
            count -= 1

    ex = JobExecutor.get_instance('flux')
    ex.set_job_status_callback(callback)
    for _ in range(count):
        job = Job(JobSpec(executable='/bin/date'))
        ex.submit(job)

    while count > 0:
        time.sleep(0.01)


Setting outputs
^^^^^^^^^^^^^^^

Dealing with errors
-------------------

Canceling your job
-------------------

Running Psi/J at your site
--------------------------

Pages should contain:

- A simple example ported to multiple sites showing how to configure PSI/J for
  each site with required configuration / attributes (with site-switcher?)
  (Each example should be in the test suite)
- Common errors you might encounter
- ‘If your site isn’t listed, please contact us to include it’


Running at LLNL LC
^^^^^^^^^^^^^^^^^^

Running at OLCF
^^^^^^^^^^^^^^^

Running at NERSC
^^^^^^^^^^^^^^^^

Running at ALCF
^^^^^^^^^^^^^^^


