import os
import pkg_resources
import subprocess
import sys

import sphinx_rtd_theme

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


src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src'))

print(src_dir + "/")

sys.path.insert(0, src_dir)

import psi


intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}
