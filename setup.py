"""
javaobj module exposes an API familiar to users of the standard library marshal,
pickle and json modules.

See:
http://download.oracle.com/javase/6/docs/platform/serialization/spec/protocol.html

:authors: Volodymyr Buell, Thomas Calmant
:license: Apache License 2.0
:version: 0.3.0
:status: Alpha

..

    Copyright 2019 Thomas Calmant

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

import os

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 3, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------


def read(fname):
    """
    Utility method to read the content of a whole file
    """
    with open(os.path.join(os.path.dirname(__file__), fname)) as fd:
        return fd.read()


# ------------------------------------------------------------------------------


setup(
    name="javaobj-py3",
    version=__version__,
    author="Volodymyr Buell",
    author_email="vbuell@gmail.com",
    maintainer="Thomas Calmant",
    maintainer_email="thomas.calmant@gmail.com",
    url="https://github.com/tcalmant/python-javaobj",
    description="Module for serializing and de-serializing Java objects.",
    license="Apache License 2.0",
    keywords="python java marshalling serialization",
    packages=["javaobj"],
    test_suite="tests.tests",
    long_description=read("README.rst"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
