import os
from setuptools import setup

setup(
    name="javaobj",
    version="0.1.0",
    author="Volodymyr Buell",
    author_email="vbuell@gmail.com",
    url="http://code.google.com/p/python-javaobj",
    description=("Module for serializing and de-serializing Java objects."),
    license="APL2",
    keywords="python java marshalling serialization",
#    packages=['javaobj'],
    py_modules = ['javaobj'],
    test_suite = "tests",
    long_description="Provides functions for reading and writing (writing is WIP currently) " \
                     "Java objects serialized or will be deserialized by ObjectOutputStream. " \
                     "This form of object representation is a standard data interchange format " \
                     "in Java world. javaobj module exposes an API familiar to users of the " \
                     "standard library marshal, pickle and json modules.",
    classifiers=[
            "Development Status :: 3 - Alpha",
            "License :: OSI Approved :: Apache Software License",
            "Topic :: Software Development :: Libraries :: Python Modules",
            ],
    )