Portable Submission Interface for Jobs (PSI/J) - Python Library
===============================================================

This is a Python library that contains the core implementation of  `the
PSI/J specification
<a href="https://exaworks.org/job-api-spec/specification>`_ as well as a
number of executors and launchers, which are the components that allow
PSI/J to communicate with specific job schedulers.

Currently supported schedulers include:

* Slurm
* LSF
* Flux
* PBS Pro
* Cobalt

.. toctree::
    :maxdepth: 2

    getting_started
    programming
    contributing
    tutorial_add_executor