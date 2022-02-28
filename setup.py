from setuptools import setup, find_packages


if __name__ == '__main__':
    
    with open('requirements.txt') as f:
        install_requires = f.readlines()

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


        packages=find_packages(where='src') + ['psij-descriptors'],
        package_dir={'': 'src'},

        package_data={
            '': ['README.md', 'LICENSE'],
            'psij.launchers.scripts': [ '*.sh' ],
            'psij.executors.batch.test': [ 'qdel', 'qstat', 'qsub', 'qrun' ],
            'psij.executors.batch': [ '**/*.mustache' ],
            'psij': ["py.typed"]
        },

        install_requires=install_requires,
        scripts=[],

        entry_points={
        },

   


        python_requires='>=3.7'
    )
