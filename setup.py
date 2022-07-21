import distutils
import io
import pathlib

from setuptools import setup, find_packages
from distutils.cmd import Command
from distutils.command.build import build


class BuildLauncherScriptsCommand(Command):

    description = '''Build the launcher scripts'''
    user_options = []

    def initialize_options(self) -> None:
        pass

    def finalize_options(self) -> None:
        pass

    def run(self) -> None:
        dir = pathlib.Path(self._get_script_dir()).resolve(strict=True)
        for file in dir.iterdir():
            if file.suffix == '.sht':
                self._build_script(file)

    def _get_script_dir(self) -> str:
        return 'src/psij/launchers/scripts'

    def _build_script(self, template_path: pathlib.Path) -> None:
        lib_path = template_path.with_name('lib.sh')
        dest_path = template_path.with_suffix('.sh')

        with dest_path.open('w') as dest:
            self._append(dest, lib_path)
            self._append(dest, template_path)

    def _append(self, dest: io.TextIOBase, src_path: pathlib.Path) -> None:
        with src_path.open('r') as src:
            for line in src:
                dest.write(line)


class CustomBuildCommand(build):
    def run(self) -> None:
        # build launcher scripts first
        BuildLauncherScriptsCommand(self.distribution).run()
        super().run()

with open('src/psij/version.py') as f:
    exec(f.read())

with open('requirements.txt') as f:
    install_requires = f.readlines()

extras_require = {
    'radical': ['radical.utils',
                'radical.pilot'],
    'saga': ['radical.saga',
             'radical.utils'],
    'dev': ['six',
            'sphinx',
            'sphinx_rtd_theme',
            'sphinx-tabs',
            # sphinx-autodoc-typehints
            'mypy >=0.790',
            'pytest',
            'flake8',
            'autopep8'],
}

if __name__ == '__main__':
    setup(
        name='psi-j-python',
        version=VERSION,

        description='''This is an implementation of the J/PSI (Portable Submission Interface for Jobs)
        specification.''',
        download_url='https://github.com/ExaWorks/psi-j-python/archive/{}.tar.gz'.format(VERSION),

        author='The ExaWorks Team',
        author_email='hategan@mcs.anl.gov',

        url='https://github.com/ExaWorks/psi-j-python',

        license='MIT License',

        classifiers=[
            'Programming Language :: Python :: 3',
            'License :: OSI Approved :: MIT License',
        ],


        packages=find_packages(where='src'),
        package_dir={'': 'src'},

        package_data={
            '': ['README.md', 'LICENSE'],
            'psij.launchers.scripts': [ '*.sh' ],
            'psij.executors.batch.test': [ 'qdel', 'qstat', 'qsub', 'qrun' ],
            'psij.executors.batch': [ '**/*.mustache' ]
        },


        scripts=[],

        entry_points={
        },
        extras_require=extras_require,
        install_requires=install_requires,
        python_requires='>=3.6',

        cmdclass={
            'launcher_scripts': BuildLauncherScriptsCommand,
            'build': CustomBuildCommand,
        },
    )
