# Low Level Development Stuff

## Building the Documentation

There are two ways to build the documentation. One is the plain one, where
the plain Sphinx output is desired, and the other is the themed version that
is meant to integrate with the website.

!!! Note

    When viewing the built docs locally, using the `file://` protocol results
    in cross-scripting issues that prevent the correct display of the
    resulting pages, such as pages being cut off at the bottom. Please use
    a simple http server as detailed below.

### Building the Standalone Documentation

1. Make sure you have the documentation dependencies installed:
    ```sh
    pip install -r requirements-docs.txt
    ```

2.  Build the actual documentation
    ```
    make docs
    ```

The output will be in `docs/.build`


### Building the Themed Documentation

This builds the themed version of the docs as well as the website. The steps
are:

1. Make sure you have the dependencies installed:
    ```sh
    pip install -r requirements-docs.txt
    ```

2. Build the website, which builds the themed version of the documentation
automatically:
    ```
    web/build.sh
    ```

Make sure that `build.sh` is called from the main directory. The output will
be in `web-build`.

3. Render the web site and themed documentation, which can be done using Jekyll.
To install Jekyll, follow these
[instructions](https://jekyllrb.com/docs/installation/). Then run

    ```
    web/serve.sh
    ```

which will output something like this:
```
...
    Server address: http://127.0.0.1:4000/psij-python/
  Server running... press ctrl-c to stop.
```


Pointing your web browser to the URL printed by Jekyll will show the PSI/J
web site. The themed documentation will be found under the "Documentation"
tab.


### Release Process

Here are the steps for putting out a fresh release to Pypi.

1. Create a new branch from main and make release specific updates:
    * Update `src/psij/version.py` to the new version number

2. Use the standard PR process and get changes from the above step merged to main.

3. Follow instructions here to [pypi docs](https://pypi.org/help/#apitoken) to
   setup tokens on your machine.

4. Run `make VERSION="version string" tag-and-release`. This will:
    * Create and push tags to GitHub.
    * Build the package.
    * Push built package to Pypi.
