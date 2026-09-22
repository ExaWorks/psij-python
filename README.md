PSI/J Web Site
==============

The web site uses Jekyll, which is a Ruby tool for static page
templating/generation. It is the tool used by Github Pages, so
it is readily deployable there *before* running Jekyll.

The web site also builds the documentation with a custom theme
that allows the Sphinx output to be directly integrated into the
main web site.

Building
========

All operations are to be done from the *root directory* of the 
PSI/J repository.

 1. Install the packages required to build the documentation 
 (this step is only needed once):
 
    ```bash
    $ sudo pip install -r requirements-docs.txt
    ```

 2. Install Jekyll prerequisites by following the instructions for your
 operating system found in the 
 [Jekyll installation instructions](https://jekyllrb.com/docs/installation/).
 You should skip installing Jekyll itself, since it will be installed by 
 *bundler*. Then run
    ```bash
    $ cd web
    $ bundle update
    $ cd ..
    ```
 to install the version of Jekyll used by github-pages. This is a one-time
 operation. For subsequent builds, you can skip directly to step 3.

 3. Run the build script, which will build the documentation, process
 files in the `web` directory, and generate the output in `web-build`:
 
    ```bash
    $ web/build.sh
    ```
 4. Run the Jekyll server with the script provided:
 
    ```bash
    $ web/serve.sh
    ```
    
You should then see something like:
```
...
    Server address: http://127.0.0.1:4000/psij-python/
  Server running... press ctrl-c to stop.
```

You can then point your browser to `http://127.0.0.1:4000/psij-python` to
see the rendered web site.
