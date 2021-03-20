#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

if __name__ == "__main__":

    with open('README.rst') as readme_file:
        readme = readme_file.read()

    with open('HISTORY.rst') as history_file:
        history = history_file.read()

    requirements = [ ]

    setup_requirements = [ ]

    test_requirements = [ ]

    setup(
        author="Sam Sterckval",
        author_email='samsterckval@gmail.com',
        python_requires='>=3.5',
        classifiers=[
            'Development Status :: 2 - Pre-Alpha',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Natural Language :: English',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
        ],
        description="A way to easily created embedded HPC systems",
        entry_points={
            'console_scripts': [
                'edgine=edgine.cli:main',
            ],
        },
        install_requires=requirements,
        license="MIT license",
        long_description=readme + '\n\n' + history,
        include_package_data=True,
        keywords='edgine',
        name='edgine',
        packages=find_packages(include=['edgine', 'edgine.*']),
        setup_requires=setup_requirements,
        test_suite='tests',
        tests_require=test_requirements,
        url='https://github.com/samsterckval/edgine',
        version='0.1.0',
        zip_safe=False,
    )
