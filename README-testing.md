Introduction
============

PSI/J comes with a testing infrastructure that allows users to contribute
tests of the PSI/J library on resources they have access to and where
running such tests is appropriate.

Contributed tests take the form of normal pytest runs for which results
are uploaded to a test aggregation service. The compatibility of various
PSI/J branches with various resources can then be assessed and is
available at https://testing.exaworks.org

How to run tests
================

There are a number of ways to run tests. Invoking `pytest` directly,
running the integration tests and through `cron` (or a similar tool).

Setting up a Cron testing job
=============================

This is the preferred way of running the tests since it allows the PSI/J
team to keep a constant eye on the state of the library on various
resources. To set up the Cron job, you can either use the provided
script:

```bash
    ./psij-ci-setup
```

or manually set up the CI runner with Cron or your favorite scheduler.


Testing with the CI runner
==========================

The CI runner is a convenience script which can clone the PSI/J
repository and run tests on several git branches. To use the CI runner:

1. Install dependencies:
```bash
    pip install --user -r requirements-dev.txt
```

2. Edit `testing.conf` and customize as needed.

3. Run tests:

```bash
    ./psij-ci-run
```

or, alternatively, using  built-in `make` target:

```bash
    make ci-tests
```


Testing with pytest
===================

This is the most direct way to run the tests and it must be done from the
main psi-j directory. Use the following steps:

1. Install dependencies:
```bash
    pip install --user -r requirements-dev.txt
```

2. Run tests:

```bash
    PYTHONPATH=$PWD/src pytest tests
```

or, alternatively, using the built-in `make` target:

```bash
    make tests
```

A number of custom options are available for tests. They are described in
detail in the `testing.conf` file. In order to use these options with
`pytest`, they can be passed as double-dashed command line arguments with
underscores converted to hyphens. For example, to run tests and
automatically upload results to the default aggregation server, you can
run:

```bash
    PYTHONPATH=$PWD/src pytest --upload-results tests
```

or, using `make`, prefix all options with a double dash ("--"):

```bash
    make tests -- --upload-results
```

Care must, however, be taken since it is impossible to preserve
whitespace and certain special characters (such as the double quotes)
when passing arguments through `make`.

