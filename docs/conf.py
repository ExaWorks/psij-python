import os
import pkg_resources
import subprocess
import sys

import sphinx_rtd_theme
from sphinx.ext.apidoc import main

needs_sphinx = '1.6'

# Set Sphinx variables
master_doc = 'index'

project = u'Portable Submission Interface for Jobs'
copyright = u'The ExaWorks Team'
release = u'0.0.1'
version = release

html_theme = 'sphinx_rtd_theme'
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
html_favicon = 'favicon.ico'
autoclass_content = 'both'
add_module_names = False
python_use_unqualified_type_names = True

# Setup Sphinx extensions (and associated variables)
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autodoc.typehints',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
]

autodoc_typehints = "description"


script_dir = os.path.normpath(os.path.dirname(__file__))
src_dir = os.path.abspath(os.path.join(script_dir, '../src'))

print(src_dir + "/")

sys.path.insert(0, src_dir)

import psij

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

# -- Setup for Sphinx API Docs -----------------------------------------------

# Workaround since sphinx does not automatically run apidoc before a build
# Copied from https://github.com/readthedocs/readthedocs.org/issues/1139

# run api doc
def run_apidoc(_):
    output_path = os.path.join(script_dir, '.generated')
    print(f"OUTPUT PATH = {output_path}")
    #exclusions = [os.path.join(src_dir, 'setup.py'),]
    main(['-f', '-o', output_path, src_dir])

# launch setup
def setup(app):
    app.connect('builder-inited', run_apidoc)
