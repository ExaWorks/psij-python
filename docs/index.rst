Portable Submission Interface for Jobs (PSI/J)
==============================================

.. image:: images/exaworks-psij-logo.png
    :width: 300px

*A Python abstraction layer over cluster schedulers*

.. image:: images/exaworks-psij.png
    :width: 350px

.. raw:: html
    
    <script src="https://kit.fontawesome.com/0f2ef02e2b.js" crossorigin="anonymous"></script>
    <div class="cards">
        <div class="card">
            <div class="icon-logo"><i class="fas fa-server" style="color: #9A3A68"></i></div>
            <h3>Write Scheduler Agnostic HPC Applications</h3>
            <p style="color: #666">
                Use a unified API to enable your HPC application to run virtually anywhere.
                <span class="psi-j-font">PSI/J</span> automatically translates abstract job
                specifications into concrete scripts and commands to send to the scheduler.
                <span class="psi-j-font">PSI/J</span> is tested on a wide variety of clusters.
            </p>
        </div>
        <div class="card">
            <div class="icon-logo"><i class="fas fa-terminal" style="color: #DD3D5A"></i></div>
            <h3><span class="psi-j-font">PSI/J</span> runs entirely in user space</h3>
            <p style="color: #666">
                There is no need to wait for infrequent deployment cycles. The HPC world
                tends to be rather dynamic and the ability to quickly integrate changes
                prompted by experimental changes in the cluster environment is essential.
            </p>
        </div>
        <div class="card">
            <div class="icon-logo"><i class="fas fa-puzzle-piece" style="color: #F15A3D"></i>
            </div>
            <h3>Use built-in or community contributed plugins</h3>
            <p style="color: #666">
                Let's be realistic. It is virtually impossible for a single entity to
                provide stable and tested adapters to all clusters and schedulers. That is
                why <span class="psi-j-font">PSI/J</span> enables and encourages community
                contributions to scheduler adapters, testbeds, and specific cluster
                knowledge.
            </p>
        </div>
        <div class="card">
            <div class="icon-logo"><i class="fas fa-save" style="color: #FDA214"></i></div>
            <h3><span class="psi-j-font">PSI/J</span> has a rich HPC legacy</h3>
            <p style="color: #666">
                The design of <span class="psi-j-font">PSI/J</span> is based on a number of
                libraries used by state of the art HPC workflow applications that the
                <span class="psi-j-font">PSI/J</span> team has worked on. Its architectural
                foundations have been tested at extreme scales and in diverse environments.
            </p>
        </div>
    </div>

.. This is a Python library that contains the core implementation of  `the
.. PSI/J specification
.. <a href="https://exaworks.org/job-api-spec/specification>`_ as well as a
.. number of executors and launchers, which are the components that allow
.. PSI/J to communicate with specific job schedulers, such as Slurm or LSF.

.. raw:: html

    <div style="margin: 2em 0">
        <img src="https://exaworks.org/images/llnl.png" style="height: 35px" />
        <img src="https://exaworks.org/images/anl-200.png" style="height: 35px; margin-left: 1em" />
        <img src="https://exaworks.org/images/bnl.png" style="height: 35px; margin-left: 1em" />
        <img src="https://exaworks.org/images/ornl.png" style="height: 30px; margin-left: 1em; vertical-align: bottom" />
    </div>
    <div style="margin: 2em 0; color: #999; font-size: 0.8em">
        <table>
            <tr>
                <td><img src="https://science.osti.gov/-/media/_/images/about/resources/logos/png/high-res/RGB_Color-Seal_Green-Mark_SC_Horizontal.png" style="height: 25px" /></td>
                <td style="padding: 0 1em">PSI/J is funded by the U.S. Department of Energy</td>
                <td><img src="https://www.ecpannualmeeting.com/images/ecp-horizontal.png" style="height: 35px" /></td>
                <td style="padding: 0 1em">PSI/J is part of the Exascale Computing Project</td>
            </tr>
        </table>
        
        
        <br />
        
        
    </div>

.. toctree::
    :hidden:
    :caption: Quickstart
    :maxdepth: 1

    installation.rst
    getting_started.rst

.. toctree::
    :hidden:
    :caption: Fundamentals
    :maxdepth: 1

    programming.rst
    api_reference.rst

.. toctree::
    :hidden:
    :caption: Contribute
    :maxdepth: 1

    contributing.rst
    tutorial_add_executor.rst

.. toctree::
    :hidden:
    :caption: Other
    :maxdepth: 1

    resources.rst
    about.rst
