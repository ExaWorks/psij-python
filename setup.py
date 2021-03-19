from setuptools import setup, find_packages

if __name__ == "__main__":
    setup(
        name="jpsi-python",
        version="0.1",

        description='''This is an implementation of the J/PSI (Portable Submission Interface for Jobs) 
        specification.''',

        author='The ExaWorks Team',
        author_email='hategan@mcs.anl.gov',

        url='https://github.com/exaworks/jpsi-python',

        classifiers=(
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
        ),


        packages={"jpsi-python": "src"},
        package_dir={"jpsi-python": "src"},

        package_data={
            '': ['README.md', 'LICENSE'],
            'jpsi-python': ['config.yaml.sample']
        },


        scripts=[],

        entry_points={
        },

        install_requires=[
        ],
    )