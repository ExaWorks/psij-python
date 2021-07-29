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
        return 'src/psi/j/launchers/scripts'

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


if __name__ == '__main__':
    setup(
        name='psi-j-python',
        version='0.1',

        description='''This is an implementation of the J/PSI (Portable Submission Interface for Jobs) 
        specification.''',

        author='The ExaWorks Team',
        author_email='hategan@mcs.anl.gov',

        url='https://github.com/exaworks/psi-j-python',

        classifiers=[
            'Programming Language :: Python :: 3',
            'License :: OSI Approved :: MIT License',
        ],


        packages=find_packages(where='src'),
        package_dir={'': 'src'},

        package_data={
            '': ['README.md', 'LICENSE'],
            'psi': ['j/launchers/scripts/*.sh']
        },


        scripts=[],

        entry_points={
        },

        install_requires=[
        ],
        python_requires='>=3.6',

        cmdclass={
            'launcher_scripts': BuildLauncherScriptsCommand,
            'build': CustomBuildCommand,
        },
    )