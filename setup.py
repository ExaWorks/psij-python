from setuptools import setup, find_packages

if __name__ == '__main__':
    setup(
        name='psi-j-python',
        version='0.1',

        description='''This is an implementation of the J/PSI (Portable Submission Interface for Jobs) 
        specification.''',

        author='The ExaWorks Team',
        author_email='hategan@mcs.anl.gov',

        url='https://github.com/exaworks/psi-j-python',

        classifiers=(
            'Programming Language :: Python :: 3',
            'License :: OSI Approved :: MIT License',
        ),


        packages=setuptools.find_packages(where='src'),
        package_dir={'': 'src'},

        package_data={
            '': ['README.md', 'LICENSE'],
            'psi-j-python': ['*.sh']
        },


        scripts=[],

        entry_points={
        },

        install_requires=[
        ],
        python_requires='>=3.6',
    )