from setuptools import setup, find_packages

with open("src/psij/version.py") as f:
    exec(f.read())


if __name__ == '__main__':
    with open('requirements.txt') as f:
        install_requires = f.readlines()

    setup(
        name='psij-python',
        version=VERSION,

        description='''This is an implementation of the PSI/J (Portable Submission Interface for Jobs) specification.''',

        author='The ExaWorks Team',
        author_email='hategan@mcs.anl.gov',

        url='https://github.com/exaworks/psij-python',

        classifiers=[
            'Programming Language :: Python :: 3',
            'License :: OSI Approved :: MIT License',
        ],


        packages=find_packages(where='src') + ['psij-descriptors'],
        package_dir={'': 'src'},

        package_data={
            '': ['README.md', 'LICENSE'],
            'psij.launchers.scripts': [ '*.sh' ],
            'psij.executors.batch.test': [ 'qdel', 'qstat', 'qsub', 'qrun' ],
            'psij.executors.batch': [ '**/*.mustache' ],
            'psij': ["py.typed"]
        },

        scripts=[],

        entry_points={
        },

        install_requires=install_requires,
        python_requires='>=3.8'
    )
