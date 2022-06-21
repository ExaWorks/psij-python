import os
from typing import List, Tuple

import pkg_resources
import subprocess
import sys

import sphinx_rtd_theme
from sphinx.ext.apidoc import main

needs_sphinx = '1.6'

# Set Sphinx variables
master_doc = 'index'

project = u'PSI/J'
copyright = u'The ExaWorks Team'
release = u'0.0.1'
version = release

html_theme = 'sphinx_rtd_theme'
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
html_favicon = 'favicon.ico'
autoclass_content = 'both'
add_module_names = False
python_use_unqualified_type_names = True
autodoc_mock_imports = ['flux']
nitpick_ignore = [
    ('py:class', 'distutils.version.StrictVersion'),
    ('py:class', 'distutils.version.Version')
]

html_sidebars = {'**': ['globaltoc.html', 'relations.html', 'sourcelink.html', 'searchbox.html']}

# Setup Sphinx extensions (and associated variables)
extensions = [
    'sphinx.ext.napoleon',
    'sphinx.ext.autodoc',
    'sphinx.ext.autodoc.typehints',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
]

autodoc_typehints = "description"
autodoc_typehints_format = "short"


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


# The following is a hack to allow returns in numpy style doctstrings to
# not duplicate the return type specified by the normal type hints.
# This was taken from https://github.com/svenevs/elba
# It was submitted as a patch to the napoleon extension. Unfortunately,
# it was rejected by the maintainers of napoleon
# (see https://github.com/sphinx-doc/sphinx/issues/7077).
def _consume_returns_section(self) -> List[Tuple[str, str, List[str]]]:
    self._consume_empty()
    desc_lines = []
    while not self._is_section_break():
        desc_lines.append(next(self._line_iter))

    return [("", "", desc_lines)]

from sphinx.ext.napoleon.docstring import NumpyDocstring
NumpyDocstring._consume_returns_section = _consume_returns_section
