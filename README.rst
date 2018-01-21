javaobj-py3
###########

.. image:: https://img.shields.io/pypi/v/javaobj-py3.svg
    :target: https://pypi.python.org/pypi/javaobj-py3/
    :alt: Latest Version

.. image:: https://img.shields.io/pypi/l/javaobj-py3.svg
    :target: https://pypi.python.org/pypi/javaobj-py3/
    :alt: License

.. image:: https://travis-ci.org/tcalmant/python-javaobj.svg?branch=master
     :target: https://travis-ci.org/tcalmant/python-javaobj
     :alt: Travis-CI status

.. image:: https://coveralls.io/repos/tcalmant/python-javaobj/badge.svg?branch=master
     :target: https://coveralls.io/r/tcalmant/python-javaobj?branch=master
     :alt: Coveralls status

*python-javaobj* is a python library that provides functions for reading and
writing (writing is WIP currently) Java objects serialized or will be
deserialized by ``ObjectOutputStream``. This form of object representation is a
standard data interchange format in Java world.

The ``javaobj`` module exposes an API familiar to users of the standard library
``marshal``, ``pickle`` and ``json`` modules.

About this repository
=====================

This project is a fork of *python-javaobj* by Volodymyr Buell, originally from
`Google Code <http://code.google.com/p/python-javaobj/>`_ and now hosted on
`GitHub <https://github.com/vbuell/python-javaobj>`_.

This fork intends to work both on Python 2.7 and Python 3.4+.

Compatibility Warning: object transformer
-----------------------------------------

As of version 0.2.0, the notion of *object transformer* from the original
project as been replaced by an *object creator*.

The *object creator* is called before the deserialization.
This allows to store the reference of the converted object before deserializing
it, and avoids a mismatch between the referenced object and the transformed one.


Compatibility Warning: bytes arrays
-----------------------------------

As of version 0.2.3, bytes arrays are loaded as a ``bytes`` object instead of
an array of integers.


Features
========

* Java object instance unmarshaling
* Java classes unmarshaling
* Primitive values unmarshaling
* Automatic conversion of Java Collections to python ones
  (``HashMap`` => ``dict``, ``ArrayList`` => ``list``, etc.)
* Basic marshalling of simple Java objects

Requirements
============

* Python >= 2.7 or Python >= 3.4
* Maven 2+ (for building test data of serialized objects.
  You can skip it if you do not plan to run ``tests.py``)

Usage
=====

Unmarshalling of Java serialised object:

.. code-block:: python

    import javaobj

    jobj = self.read_file("obj5.ser")
    pobj = javaobj.loads(jobj)
    print(pobj)

Or, you can use Unmarshaller object directly:

.. code-block:: python

    import javaobj

    marshaller = javaobj.JavaObjectUnmarshaller(open("objCollections.ser"))
    pobj = marshaller.readObject()

    self.assertEqual(pobj.value, 17)
    self.assertTrue(pobj.next)

    pobj = marshaller.readObject()
