# Low Level Development Stuff

## Building the Documentation

There are two ways to build the documentation. One is the plain one, where
the plain Sphinx output is desired, and the other is the themed version that
is meant to integrate with the web site.

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

This builds the themed version of the docs as well as the web site. The steps
are:

1. Make sure you have the dependencies installed:
    ```sh
    pip install -r requirements-docs.txt
    ```

2. Build the web site, which builds the themed version of the documentation
automatically:
    ```
    web/build.sh
    ```

Make sure that `build.sh` is called from the main directory. The output will
be in `web-build`. You are likely going to need to load it through a web
server. A simple way to do so is:

    ```
    cd web-build
    python -m http.server <port>
    ```

where `<port>` is a port number to start the HTTP server on.

When developing the web site, a convenient script is `web/watch.sh`, which can
monitor the source directories and re-build when files are modified. This
requires `inotify` which may or may not be available on your platform.
