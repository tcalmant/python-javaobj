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

Compatibility Warnings
======================

New implementation of the parser
--------------------------------

:Implementations: ``v1``, ``v2``
:Version: ``0.4.0+``

Since version 0.4.0, two implementations of the parser are available:

* ``v1``: the *classic* implementation of ``javaobj``, with a work in progress
  implementation of a writer.
* ``v2``: the *new* implementation, which is a port of the Java project
  `jdeserialize <https://github.com/frohoff/jdeserialize/>`_,
  with support of the object transformer (with a new API) and of the ``numpy``
  arrays loading.

You can use the ``v1`` parser to ensure that the behaviour of your scripts
doesn't change and to keep the ability to write down files.

You can use the ``v2`` parser for new developments
*which won't require marshalling* and as a *fallback* if the ``v1``
fails to parse a file.

Object transformers V1
----------------------

:Implementations: ``v1``
:Version: ``0.2.0+``

As of version 0.2.0, the notion of *object transformer* from the original
project as been replaced by an *object creator*.

The *object creator* is called before the deserialization.
This allows to store the reference of the converted object before deserializing
it, and avoids a mismatch between the referenced object and the transformed one.

Object transformers V2
----------------------

:Implementations: ``v2``
:Version: ``0.4.0+``

The ``v2`` implementation provides a new API for the object transformers.
Please look at the *Usage (V2)* section in this file.

Bytes arrays
------------

:Implementations: ``v1``
:Version: ``0.2.3+``

As of version 0.2.3, bytes arrays are loaded as a ``bytes`` object instead of
an array of integers.

Custom Transformer
------------------

:Implementations: ``v2``
:Version: ``0.4.1+``

A new transformer API has been proposed to handle objects written with a custom
Java writer.
You can find a sample usage in the *Custom Transformer* section in this file.

Features
========

* Java object instance un-marshalling
* Java classes un-marshalling
* Primitive values un-marshalling
* Automatic conversion of Java Collections to python ones
  (``HashMap`` => ``dict``, ``ArrayList`` => ``list``, etc.)
* Basic marshalling of simple Java objects (``v1`` implementation only)

Requirements
============

* Python >= 2.7 or Python >= 3.4
* ``enum34`` and ``typing`` when using Python <= 3.4 (installable with ``pip``)
* Maven 2+ (for building test data of serialized objects.
  You can skip it if you do not plan to run ``tests.py``)

Usage (V1 implementation)
=========================

Un-marshalling of Java serialised object:

.. code-block:: python

   import javaobj

   with open("obj5.ser", "rb") as fd:
       jobj = fd.read()

   pobj = javaobj.loads(jobj)
   print(pobj)

Or, you can use ``JavaObjectUnmarshaller`` object directly:

.. code-block:: python

   import javaobj

   with open("objCollections.ser", "rb") as fd:
       marshaller = javaobj.JavaObjectUnmarshaller(fd)
       pobj = marshaller.readObject()

       print(pobj.value, "should be", 17)
       print(pobj.next, "should be", True)

       pobj = marshaller.readObject()


**Note:** The objects and methods provided by ``javaobj`` module are shortcuts
to the ``javaobj.v1`` package, for Compatibility purpose.
It is **recommended** to explicitly import methods and classes from the ``v1``
(or ``v2``) package when writing new code, in order to be sure that your code
won't need import updates in the future.


Usage (V2 implementation)
=========================

The following methods are provided by the ``javaobj.v2`` package:

* ``load(fd, *transformers, use_numpy_arrays=False)``:
  Parses the content of the given file descriptor, opened in binary mode (`rb`).
  The method accepts a list of custom object transformers. The default object
  transformer is always added to the list.

  The ``use_numpy_arrays`` flag indicates that the arrays of primitive type
  elements must be loaded using ``numpy`` (if available) instead of using the
  standard parsing technic.

* ``loads(bytes, *transformers, use_numpy_arrays=False)``:
  This the a shortcut to the ``load()`` method, providing it the binary data
  using a ``BytesIO`` object.

**Note:** The V2 parser doesn't have the marshalling capability.

Sample usage:

.. code-block:: python

   import javaobj.v2 as javaobj

   with open("obj5.ser", "rb") as fd:
       pobj = javaobj.load(fd)

   print(pobj.dump())


Object Transformer
-------------------

An object transformer can be called during the parsing of a Java object
instance or while loading an array.

The Java object instance parsing works in two main steps:

1. The transformer is called to create an instance of a bean that inherits
   ``JavaInstance``.
2. The latter bean is then called:

   * When the object is written with a custom block data
   * After the fields and annotations have been parsed, to update the content of
     the Python bean.

Here is an example for a Java ``HashMap`` object. You can look at the code of
the ``javaobj.v2.transformer`` module to see the whole implementation.

.. code-block:: python

   class JavaMap(dict, javaobj.v2.beans.JavaInstance):
       """
       Inherits from dict for Python usage, JavaInstance for parsing purpose
       """
       def __init__(self):
           # Don't forget to call both constructors
           dict.__init__(self)
           JavaInstance.__init__(self)

      def load_from_blockdata(self, parser, reader, indent=0):
        """
        Reads content stored in a block data.

        This method is called only if the class description has both the
        ``SC_EXTERNALIZABLE`` and ``SC_BLOCK_DATA`` flags set.

        The stream parsing will stop and fail if this method returns False.

        :param parser: The JavaStreamParser in use
        :param reader: The underlying data stream reader
        :param indent: Indentation to use in logs
        :return: True on success, False on error
        """
        # This kind of class is not supposed to have the SC_BLOCK_DATA flag set
        return False

       def load_from_instance(self, indent=0):
           # type: (int) -> bool
           """
           Load content from the parsed instance object.

           This method is called after the block data (if any), the fields and
           the annotations have been loaded.

           :param indent: Indentation to use while logging
           :return: True on success (currently ignored)
           """
           # Maps have their content in their annotations
           for cd, annotations in self.annotations.items():
               # Annotations are associated to their definition class
               if cd.name == "java.util.HashMap":
                   # We are in the annotation created by the handled class
                   # Group annotation elements 2 by 2
                   # (storage is: key, value, key, value, ...)
                   args = [iter(annotations[1:])] * 2
                   for key, value in zip(*args):
                       self[key] = value

                   # Job done
                   return True

           # Couldn't load the data
           return False

   class MapObjectTransformer(javaobj.v2.api.ObjectTransformer):
       """
       Creates a JavaInstance object with custom loading methods for the
       classes it can handle
       """
       def create_instance(self, classdesc):
           # type: (JavaClassDesc) -> Optional[JavaInstance]
           """
           Transforms a parsed Java object into a Python object

           :param classdesc: The description of a Java class
           :return: The Python form of the object, or the original JavaObject
           """
           if classdesc.name == "java.util.HashMap":
               # We can handle this class description
               return JavaMap()
           else:
               # Return None if the class is not handled
               return None

Custom Transformer
------------------

The custom transformer is called when the class is not handled by the default
object transformer.


The sample given here is used in the unit tests.

On the Java side, we create various classes and write them as we wish:

.. code-block:: java

   class CustomClass implements Serializable {
   	private static final long serialVersionUID = 1;

       public void start(ObjectOutputStream out) throws Exception {
           this.writeObject(out);
       }

       private void writeObject(ObjectOutputStream out) throws IOException {
           CustomWriter custom = new CustomWriter(42);
           out.writeObject(custom);
           out.flush();
       }
   }

   class RandomChild extends Random {
   	private static final long serialVersionUID = 1;
       private int num = 1;
       private double doub = 4.5;

       RandomChild(int seed) {
           super(seed);
       }
   }

   class CustomWriter implements Serializable {
       protected RandomChild custom_obj = null;

       CustomWriter(int seed) {
           custom_obj = new RandomChild(seed);
       }

       private static final long serialVersionUID = 1;
       private static final int CURRENT_SERIAL_VERSION = 0;
       private void writeObject(ObjectOutputStream out) throws IOException {
           out.writeInt(CURRENT_SERIAL_VERSION);
           out.writeObject(custom_obj);
       }
   }

An here is a sample writing of that kind of object:

.. code-block:: java

   ObjectOutputStream oos = new ObjectOutputStream(
       new FileOutputStream("custom_objects.ser"));
   CustomClass writer = new CustomClass();
   writer.start(oos);
   oos.flush();
   oos.close();


On the Python side, the first step is to define the custom transformers.
They are children of the ``javaobj.v2.transformers.ObjectTransformer`` class.

.. code-block:: python

   class BaseTransformer(javaobj.v2.transformers.ObjectTransformer):
       """
       Creates a JavaInstance object with custom loading methods for the
       classes it can handle
       """

       def __init__(self, handled_classes={}):
           self.instance = None
           self.handled_classes = handled_classes

       def create_instance(self, classdesc):
           """
           Transforms a parsed Java object into a Python object

           :param classdesc: The description of a Java class
           :return: The Python form of the object, or the original JavaObject
           """
           if classdesc.name in self.handled_classes:
               self.instance = self.handled_classes[classdesc.name]()
               return self.instance

           return None

   class RandomChildTransformer(BaseTransformer):
       def __init__(self):
           super(RandomChildTransformer, self).__init__({'RandomChild': RandomChildInstance})

   class CustomWriterTransformer(BaseTransformer):
       def __init__(self):
           super(CustomWriterTransformer, self).__init__({'CustomWriter': CustomWriterInstance})

   class JavaRandomTransformer(BaseTransformer):
       def __init__(self):
           super(JavaRandomTransformer, self).__init__()
           self.name = "java.util.Random"
           self.field_names = ['haveNextNextGaussian', 'nextNextGaussian', 'seed']
           self.field_types = [
               javaobj.v2.beans.FieldType.BOOLEAN,
               javaobj.v2.beans.FieldType.DOUBLE,
               javaobj.v2.beans.FieldType.LONG
           ]

       def load_custom_writeObject(self, parser, reader, name):
           if name == self.name:
               fields = []
               values = []
               for index, value in enumerate(self.field_types):
                   values.append(parser._read_field_value(value))
                   fields.append(javaobj.v2.beans.JavaField(value, self.field_names[index]))

               class_desc = javaobj.v2.beans.JavaClassDesc(
                   javaobj.v2.beans.ClassDescType.NORMALCLASS)
               class_desc.name = self.name
               class_desc.desc_flags = javaobj.v2.beans.ClassDataType.EXTERNAL_CONTENTS
               class_desc.fields = fields
               class_desc.field_data = values
               return class_desc
           return None

Second step is defining the representation of the instances, where the real
object loading occurs. Those classes inherit from
``javaobj.v2.beans.JavaInstance``.

.. code-block:: python

   # Custom writeObject parsing classes
   class CustomWriterInstance(javaobj.v2.beans.JavaInstance):
       def __init__(self):
           javaobj.v2.beans.JavaInstance.__init__(self)

       def load_from_instance(self):
           """
           Updates the content of this instance
           from its parsed fields and annotations
           :return: True on success, False on error
           """
           if self.classdesc and self.classdesc in self.annotations:
               fields = ['int_not_in_fields'] + self.classdesc.fields_names
               raw_data = self.annotations[self.classdesc]
               int_not_in_fields = struct.unpack(
                   '>i', BytesIO(raw_data[0].data).read(4))[0]
               custom_obj = raw_data[1]
               values = [int_not_in_fields, custom_obj]
               self.field_data = dict(zip(fields, values))
               return True

           return False


   class RandomChildInstance(javaobj.v2.beans.JavaInstance):
       def load_from_instance(self):
           """
           Updates the content of this instance
           from its parsed fields and annotations
           :return: True on success, False on error
           """
           if self.classdesc and self.classdesc in self.field_data:
               fields = self.classdesc.fields_names
               values = [self.field_data[self.classdesc][self.classdesc.fields[i]] for i in range(len(fields))]
               self.field_data = dict(zip(fields, values))
               if self.classdesc.super_class and self.classdesc.super_class in self.annotations:
                   super_class = self.annotations[self.classdesc.super_class][0]
                   self.annotations = dict(zip(super_class.fields_names, super_class.field_data))
               return True

           return False


Finally we can use the transformers in the loading process.
Note that even if it is not explicitly given, the ``DefaultObjectTransformer``
will be also be used, as it is added automatically by ``javaobj`` if it is
missing from the given list.

.. code-block:: python

   # Load the object using those transformers
   transformers = [
       CustomWriterTransformer(),
       RandomChildTransformer(),
       JavaRandomTransformer()
   ]
   pobj = javaobj.loads("custom_objects.ser", *transformers)

   # Here we show a field that doesn't belong to the class
   print(pobj.field_data["int_not_in_fields"]
