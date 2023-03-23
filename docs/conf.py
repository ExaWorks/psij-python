import os
from typing import List, Tuple

import pkg_resources
import subprocess
import sys

import sphinx_rtd_theme
from sphinx.ext.apidoc import main

web_docs = False
if 'PSIJ_WEB_DOCS' in os.environ:
	web_docs = True

needs_sphinx = '1.6'

# Set Sphinx variables
master_doc = 'index'

project = u'PSI/J'
copyright = u'The ExaWorks Team'
if web_docs:
	html_theme = 'cloud'
else:
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

if web_docs:
    templates_path = ['_templates']
    # Unfortunately sphinx-multiversion does not properly deal with 
    # setting the title to the proper version. You either get some
    # default like "0.0.1" or you get whatever the current conf.py
    # sets (i.e., the latest version).
    # See, e.g., https://github.com/Holzhaus/sphinx-multiversion/issues/61
    #
    # But we already have the version selector that displays the version,
    # so we can display that where the broken version would otherwise
    # have appeared.
    html_title = "PSI/J"
    # Multi-version
    smv_branch_whitelist = '^matchmeifyoucan$'
    smv_remote_whitelist = None
    smv_released_pattern = r'^\d+\.\d+\.\d+(\..*)?$'
    smv_outputdir_format = 'v/{ref.name}'


html_sidebars = {'**': ['globaltoc.html', 'relations.html', 'sourcelink.html', 'searchbox.html']}

# These are needed for the dhtml trickery
html_static_path = ["_static"]
html_js_files = ["extras.js"]
html_css_files = ["extras.css"]

# Setup Sphinx extensions (and associated variables)
extensions = [
    'sphinx.ext.napoleon',
    'sphinx.ext.autodoc',
    'sphinx.ext.autodoc.typehints',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
]

if web_docs:
    extensions.append('sphinx_multiversion')

autodoc_typehints = "description"
autodoc_typehints_format = "short"

release = None
version = None
src_dir = None

def read_version(docs_dir):
    global release, version, src_dir
    src_dir = os.path.abspath(os.path.join(docs_dir, '../src'))

    sys.path.insert(0, src_dir)

    import psij
    release = psij.__version__
    version = release


my_dir = os.path.normpath(os.path.dirname(__file__))
read_version(my_dir)

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

# -- Setup for Sphinx API Docs -----------------------------------------------

# Workaround since sphinx does not automatically run apidoc before a build
# Copied from https://github.com/readthedocs/readthedocs.org/issues/1139

# run api doc
def run_apidoc(sphinx):
    read_version(sphinx.srcdir)  # this sets src_dir based on the version being compiled
    output_path = os.path.join(sphinx.srcdir, '.generated')
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
