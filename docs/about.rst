.. _about:

About
=====

The motivation behind PSI/J
***************************

The `ExaWorks <https://exaworks.org>`_ project is a community-led project 
under the umbrella of the `Exascale Computing Project <file:///Users/8uf/Documents/workspace/psi-j-python/web/exascaleproject.org>`_ 
which brings together a number of high level HPC tools developed by the 
members of ExaWorks. We noticed that most of these projects, as well as many 
of the community projects implemented a software layer/library to interact with 
HPC schedulers in order to insulate the core functionality from the details of 
how things are specified for each scheduler. We also noticed that the 
respective libraries mostly covered schedulers running on resources that each 
team had access to. We figured that we could use our combined knowledge to 
design a single API/library for this goal, a library that would be tested on 
all resources that all ExaWorks teams have access to. We could then share this 
API and library so that all high level HPC tools could benefit from it.

The complexity of testing HPC libraries
***************************************

A major factor contributing to the difficulties in maintaining HPC software 
tools is that access to HPC resources is generally limited to a small number of 
clusters local to each team. Additionally, HPC resources tend to vary widely 
depending on the institution that maintains them. Consequently, the chances 
that software that is tested on resources that a HPC tool development team has 
access to will encounter problems on other HPC resources is fairly high. As 
mentioned above, a first step in addressing this problem is by pooling the 
teams' respective resources for testing purposes. However, PSI/J takes it a 
step further by exposing an infrastructure that allows any user PSI/J user to 
easily contribute test results to the PSI/J, and do so automatically. This is 
a mutually beneficial relationship: the PSI/J community at large gains a 
certain level of assurance that PSI/J functions correctly on a wide range of 
resources, while users contributing tests have a mechanism to ensure that the 
PSI/J team is aware of potential problems specific to their resources and can 
address them, thus ensuring that PSI/J continues to function correctly on 
specific resources.


Precursors to PSI/J
*******************

SAGA
----

SAGA — an `OGF standard <http://dx.doi.org/10.1016/j.softx.2015.03.001>`_ — 
abstracts away the specificity of diverse queue systems, offering a consistent 
representation of jobs and of the capabilities required to submit them to the 
resources. `RADICAL-SAGA <https://github.com/radical-cybertools/radical.saga>`_ 
implements a subset of the SAGA standard, exposing a homogeneous programming 
interface to the batch systems of HPC and HTC resources, enabling job 
submissions and file transfers across resources. RADICAL-SAGA is used by 
`RADICAL-Pilot <https://github.com/radical-cybertools/radical.pilot>`_ to 
acquire resources and staging data to and from HPC platforms. PSI/J will 
replace RADICAL-SAGA, offering streamlined capabilities and a modern 
implementation.

Java CoG Kit
------------

The PSI/J API is in no small part inspired by the Java CoG Kit 
`Abstraction API <https://ieeexplore.ieee.org/document/1271452>`_. The 
`Swift <https://swift-lang.org>`_ workflow system made extensive use of and 
improved on the Java Cog Kit Abstraction API. While the original Swift 
(Swift/K) is not maintained any more, its two spiritual successors, 
`Swift/T <http://swift-lang.org/Swift-T/>`_ and `Parsl <https://parsl-project.org/>`_ 
are.
