# javaobj-py3

[![GitHub repository](https://img.shields.io/badge/GitHub-Repository-black?logo=github)](https://github.com/tcalmant/python-javaobj/)
[![Latest Version](https://img.shields.io/pypi/v/javaobj-py3.svg)](https://pypi.python.org/pypi/javaobj-py3/)
[![License](https://img.shields.io/pypi/l/javaobj-py3.svg)](https://pypi.python.org/pypi/javaobj-py3/)
[![CI Build](https://github.com/tcalmant/python-javaobj/actions/workflows/build-24.04.yml/badge.svg?branch=v3)](https://github.com/tcalmant/python-javaobj/actions/workflows/build-24.04.yml)
[![Coveralls status](https://coveralls.io/repos/tcalmant/python-javaobj/badge.svg?branch=master)](https://coveralls.io/r/tcalmant/python-javaobj?branch=master)

*python-javaobj* is a python library that provides functions for reading and
writing Java objects serialized or to be deserialized by `ObjectOutputStream`.
This form of object representation is a standard data interchange format in
Java world.

The `javaobj` module exposes an API familiar to users of the standard library
`marshal`, `pickle` and `json` modules.

## About this repository

This project is a fork of *python-javaobj* by Volodymyr Buell, originally from
[Google Code](http://code.google.com/p/python-javaobj/) and now hosted on
[GitHub](https://github.com/vbuell/python-javaobj).

This fork intends to work both on Python 2.7 and Python 3.4+.

## Compatibility Warnings

### New implementation of the parser

| Implementations | Version  |
|-----------------|----------|
| `v1`, `v2`      | `0.4.0+` |
| `v3`            | `0.5.0+` |

Since version 0.4.0, three implementations of the parser are available:

* `v1`: the *classic* implementation of `javaobj`, with a work in progress
  implementation of a writer.
* `v2`: a rewritten implementation, which is a port of the Java project
  [`jdeserialize`](https://github.com/frohoff/jdeserialize/),
  with support of the object transformer (with a new API) and of the `numpy`
  arrays loading.
* `v3`: a **new** implementation, written from scratch to benefit from
  Python 3.12+ features, with full read **and** write support.

You can use the `v1` parser to ensure that the behaviour of your scripts
doesn't change.  It also provides a basic marshalling capability.

You can use the `v2` parser for developments in Python versions lower
than 3.12 and *which won't require marshalling*, or as a *fallback*
if the `v1` parser fails to parse a file.

For new development, you should use the `v3` parser, which supports both
reading and writing Java object streams.

### Object transformers V1

| Implementations | Version  |
|-----------------|----------|
| `v1`            | `0.2.0+` |

As of version 0.2.0, the notion of *object transformer* from the original
project as been replaced by an *object creator*.

The *object creator* is called before the deserialization.
This allows to store the reference of the converted object before deserializing
it, and avoids a mismatch between the referenced object and the transformed one.

### Object transformers V2

| Implementations | Version  |
|-----------------|----------|
| `v2`            | `0.4.0+` |

The `v2` implementation provides a new API for the object transformers.
Please look at the *Usage (V2)* section in this file.

### Object transformers V3

| Implementations | Version  |
|-----------------|----------|
| `v3`            | `0.5.0+` |

The `v3` implementation is a full rewrite targeting **Python 3.12+**.
It uses `dataclasses`, structural pattern matching (`match/case`) and PEP 604
union types.  Its API is intentionally similar to `v2` but fixes several
correctness issues and adds stricter safety limits.
Please look at the *Usage (V3)* and *Migration to V3* sections in this file.

### Bytes arrays

| Implementations | Version  |
|-----------------|----------|
| `v1`            | `0.2.3+` |

As of version 0.2.3, bytes arrays are loaded as a `bytes` object instead of
an array of integers.

### Custom Transformer

| Implementations | Version  |
|-----------------|----------|
| `v2`            | `0.4.2+` |

A new transformer API has been proposed to handle objects written with a custom
Java writer.
You can find a sample usage in the *Custom Transformer* section in this file.

## Features

* Java object instance un-marshalling
* Java classes un-marshalling
* Primitive values un-marshalling
* Automatic conversion of Java Collections to python ones
  (`HashMap` => `dict`, `ArrayList` => `list`, etc.)
* Basic marshalling of simple Java objects (`v1` implementation)
* Full marshalling of Java object streams (`v3` implementation)
* Automatically uncompresses GZipped files

## Requirements

* Python >= 2.7 or Python >= 3.4 for `v1` and `v2`
* Python >= 3.12 for `v3`
* `enum34` and `typing` when using Python <= 3.4 (installable with `pip`)
* Maven 2+ (for building test data of serialized objects.
  You can skip it if you do not plan to run `tests.py`)

## Usage (V1 implementation)

Un-marshalling of Java serialised object:

```python
import javaobj

with open("obj5.ser", "rb") as fd:
    jobj = fd.read()

pobj = javaobj.loads(jobj)
print(pobj)
```

Or, you can use `JavaObjectUnmarshaller` object directly:

```python
import javaobj

with open("objCollections.ser", "rb") as fd:
    marshaller = javaobj.JavaObjectUnmarshaller(fd)
    pobj = marshaller.readObject()

    print(pobj.value, "should be", 17)
    print(pobj.next, "should be", True)

    pobj = marshaller.readObject()
```

**Note:** The objects and methods provided by `javaobj` module are shortcuts
to the `javaobj.v1` package, for Compatibility purpose.
It is **recommended** to explicitly import methods and classes from the `v1`,
`v2`, or `v3` package when writing new code, in order to be sure that your code
won't need import updates in the future.


## Usage (V2 implementation)

The following methods are provided by the `javaobj.v2` package:

* `load(fd, *transformers, use_numpy_arrays=False)`:
  Parses the content of the given file descriptor, opened in binary mode (`rb`).
  The method accepts a list of custom object transformers. The default object
  transformer is always added to the list.

  The `use_numpy_arrays` flag indicates that the arrays of primitive type
  elements must be loaded using `numpy` (if available) instead of using the
  standard parsing technic.

* `loads(bytes, *transformers, use_numpy_arrays=False)`:
  This the a shortcut to the `load()` method, providing it the binary data
  using a `BytesIO` object.

**Note:** The V2 parser doesn't have the marshalling capability.

Sample usage:

```python
import javaobj.v2 as javaobj

with open("obj5.ser", "rb") as fd:
    pobj = javaobj.load(fd)

print(pobj.dump())
```

### Object Transformer

An object transformer can be called during the parsing of a Java object
instance or while loading an array.

The Java object instance parsing works in two main steps:

1. The transformer is called to create an instance of a bean that inherits
   `JavaInstance`.
1. The latter bean is then called:

   * When the object is written with a custom block data
   * After the fields and annotations have been parsed, to update the content
   of the Python bean.

Here is an example for a Java `HashMap` object. You can look at the code of
the `javaobj.v2.transformer` module to see the whole implementation.

```python
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
    `SC_EXTERNALIZABLE` and `SC_BLOCK_DATA` flags set.

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
```

### Custom Object Transformer

The custom transformer is called when the class is not handled by the default
object transformer.
A custom object transformer still inherits from the `ObjectTransformer` class,
but it also implements the `load_custom_writeObject` method.

The sample given here is used in the unit tests.

#### Java sample

On the Java side, we create various classes and write them as we wish:

```java
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
    protected RandomChild custom_obj;

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
```

An here is a sample writing of that kind of object:

```java
ObjectOutputStream oos = new ObjectOutputStream(
    new FileOutputStream("custom_objects.ser"));
CustomClass writer = new CustomClass();
writer.start(oos);
oos.flush();
oos.close();
```

#### Python sample

On the Python side, the first step is to define the custom transformers.
They are children of the `javaobj.v2.transformers.ObjectTransformer` class.

```python
class BaseTransformer(javaobj.v2.transformers.ObjectTransformer):
    """
    Creates a JavaInstance object with custom loading methods for the
    classes it can handle
    """

    def __init__(self, handled_classes=None):
        self.instance = None
        self.handled_classes = handled_classes or {}

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
        super(RandomChildTransformer, self).__init__(
            {"RandomChild": RandomChildInstance}
        )

class CustomWriterTransformer(BaseTransformer):
    def __init__(self):
        super(CustomWriterTransformer, self).__init__(
            {"CustomWriter": CustomWriterInstance}
        )

class JavaRandomTransformer(BaseTransformer):
    def __init__(self):
        super(JavaRandomTransformer, self).__init__()
        self.name = "java.util.Random"
        self.field_names = ["haveNextNextGaussian", "nextNextGaussian", "seed"]
        self.field_types = [
            javaobj.v2.beans.FieldType.BOOLEAN,
            javaobj.v2.beans.FieldType.DOUBLE,
            javaobj.v2.beans.FieldType.LONG,
        ]

    def load_custom_writeObject(self, parser, reader, name):
        if name != self.name:
            return None

        fields = []
        values = []
        for f_name, f_type in zip(self.field_names, self.field_types):
            values.append(parser._read_field_value(f_type))
            fields.append(javaobj.v2.beans.JavaField(f_type, f_name))

        class_desc = javaobj.v2.beans.JavaClassDesc(
            javaobj.v2.beans.ClassDescType.NORMALCLASS
        )
        class_desc.name = self.name
        class_desc.desc_flags = javaobj.v2.beans.ClassDataType.EXTERNAL_CONTENTS
        class_desc.fields = fields
        class_desc.field_data = values
        return class_desc
```

Second step is defining the representation of the instances, where the real
object loading occurs. Those classes inherit from
`javaobj.v2.beans.JavaInstance`.

```python
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
            # Here, we known there is something written before the fields,
            # even if it's not declared in the class description
            fields = ["int_not_in_fields"] + self.classdesc.fields_names
            raw_data = self.annotations[self.classdesc]
            int_not_in_fields = struct.unpack(
                ">i", BytesIO(raw_data[0].data).read(4)
            )[0]
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
            values = [
                self.field_data[self.classdesc][self.classdesc.fields[i]]
                for i in range(len(fields))
            ]
            self.field_data = dict(zip(fields, values))
            if (
                self.classdesc.super_class
                and self.classdesc.super_class in self.annotations
            ):
                super_class = self.annotations[self.classdesc.super_class][0]
                self.annotations = dict(
                    zip(super_class.fields_names, super_class.field_data)
                )
            return True

        return False
```

Finally we can use the transformers in the loading process.
Note that even if it is not explicitly given, the `DefaultObjectTransformer`
will be also be used, as it is added automatically by `javaobj` if it is
missing from the given list.

```python
# Load the object using those transformers
transformers = [
    CustomWriterTransformer(),
    RandomChildTransformer(),
    JavaRandomTransformer()
]
with open("custom_objects.ser", "rb") as fd:
    pobj = javaobj.load(fd, *transformers)

# Here we show a field that isn't visible from the class description
# The field belongs to the class but it's not serialized by default because
# it's static. See: https://stackoverflow.com/a/16477421/12621168
print(pobj.field_data["int_not_in_fields"])
```

## Usage (V3 implementation)

> **Requires Python 3.12+.**

The `javaobj.v3` package is a full rewrite of the Java object stream parser.
It provides the same two entry-points as `v2`:

* `load(fd, *transformers, use_numpy_arrays=False, max_array_size=…, max_depth=500)`:
  Parses a binary file descriptor opened in `rb` mode and returns the top-level
  object if the stream contains exactly one, a list of objects if there are
  several, or `None` for an empty stream.  Pass additional `ObjectTransformer`
  instances as positional arguments.

* `loads(data, *transformers, …)`:
  Convenience wrapper around `load()` that accepts `bytes`.

Sample usage:

```python
import javaobj.v3 as javaobj

with open("obj5.ser", "rb") as fd:
    pobj = javaobj.load(fd)

# Access fields by name (preferred)
value = pobj.get_field("myField")

# Or use attribute-style access (issues a warning on ambiguity)
value = pobj.myField
```

### New features in V3

| Feature | V1 | V2 | V3 |
|---|---|---|---|
| Python 3.12+ (`match/case`, PEP 604) | ✗ | ✗ | ✓ |
| Fully typed (`dataclasses`, PEP 695 `type` aliases) | ✗ | partial | ✓ |
| `TC_RESET` handling | ✗ | ✗ | ✓ |
| `TC_EXCEPTION` in object graph | ✗ | ✗ | ✓ |
| `TC_PROXYCLASSDESC` | ✗ | ✓ | ✓ |
| Security limits (max depth / array size) | ✗ | ✗ | ✓ |
| Correct `TYPE_CHAR` numpy dtype (`>u2`) | ✗ | ✗ | ✓ |
| Typed exception hierarchy | ✗ | ✗ | ✓ |
| `BlockData.__eq__(bytes)` compatibility | ✓ | ✓ | ✓ |
| Marshalling (writing) support | partial | ✗ | ✓ |

### Security limits

`v3` adds two optional safety limits that prevent resource exhaustion when
parsing untrusted streams:

```python
import javaobj.v3 as javaobj

with open("untrusted.ser", "rb") as fd:
    pobj = javaobj.load(
        fd,
        max_array_size=10 * 1024 * 1024,  # 10 MiB max per array
        max_depth=100,                      # max object-graph depth
    )
```

### Object Transformer V3

The `ObjectTransformer` base class in `v3` has the same three override points
as in `v2`:

* `create_instance(classdesc)` — return a `JavaInstance` subclass (or `None`
  to fall back to the next transformer).
* `load_array(reader, type_code, size)` — called for `TC_ARRAY` records;
  return the array data (`bytes` or `list`) or `None` to use the default logic.
* `load_custom_writeObject(parser, reader, class_name)` — called when a
  class written with `writeObject()` requires fully custom parsing.

The `DefaultObjectTransformer` additionally exposes a public `handles(name)`
method that returns `True` when the transformer knows how to load the given
Java class name.

### Using NumPy arrays (V3)

```python
import javaobj.v3 as javaobj

with open("arrays.ser", "rb") as fd:
    pobj = javaobj.load(fd, use_numpy_arrays=True)
```

When `use_numpy_arrays=True`, a `NumpyArrayTransformer` is appended to the
transformer list and primitive arrays are returned as `numpy.ndarray`.

### Marshalling / Writing (V3)

The `javaobj.v3` package exposes two additional entry-points for serializing
beans back to the Java Object Serialization binary format:

* `dump(fd, *objects)`: Writes one or more parsed objects to a binary file
  descriptor opened in `wb` mode.
* `dumps(*objects) -> bytes`: Returns the serialized stream as a `bytes`
  object.

Both functions accept any combination of
`JavaInstance`, `JavaArray`, `JavaString`, `JavaEnum`, `JavaClass`, `BlockData`,
and `None` (written as `TC_NULL`) as positional arguments.

#### Simple round-trip

```python
import javaobj.v3 as javaobj

# Parse an existing file
with open("obj5.ser", "rb") as fd:
    pobj = javaobj.load(fd)

# Serialize back to bytes
data = javaobj.dumps(pobj)

# Or write directly to a file
with open("obj5_copy.ser", "wb") as fd:
    javaobj.dump(fd, pobj)
```

#### Writing multiple objects

```python
import javaobj.v3 as javaobj
from javaobj.v3.beans import JavaString

with open("a.ser", "rb") as fd:
    obj_a = javaobj.load(fd)

# Write two objects into one stream
data = javaobj.dumps(obj_a, JavaString("hello"))

# Re-parse: returns a list when the stream holds more than one object
result = javaobj.loads(data)   # -> [obj_a, JavaString("hello")]
```

#### Supported constructs

| Construct | Supported |
|---|---|
| `TC_OBJECT` — `NOWRCLASS` (plain fields only) | ✓ |
| `TC_OBJECT` — `WRCLASS` (fields + block-data annotations) | ✓ |
| `TC_ARRAY` | ✓ |
| `TC_STRING` / `TC_LONGSTRING` | ✓ |
| `TC_ENUM` | ✓ |
| `TC_CLASS` | ✓ |
| `TC_NULL` | ✓ |
| `TC_BLOCKDATA` / `TC_BLOCKDATALONG` | ✓ |
| `TC_PROXYCLASSDESC` | ✓ |
| Back-references (`TC_REFERENCE`) | ✓ (automatic) |
| `EXTERNAL_CONTENTS` (Protocol v1 `Externalizable`) | ✗ |

> **Note:** Back-references are tracked automatically by identity: if the same
> object appears more than once in the graph, subsequent occurrences are
> written as `TC_REFERENCE` — exactly as Java's `ObjectOutputStream` does.

#### Building a Java object from scratch

You can construct the v3 beans manually to serialize a Python object as if it
were a Java one.  The key types are:

* `JavaClassDesc` — the class descriptor (name, `serialVersionUID`, flags,
  fields)
* `JavaField` — one field entry (type code + name, and optionally the binary
  class name for object/array fields)
* `JavaInstance` — the object instance (`field_data` maps each class
  descriptor to a `{JavaField: value}` dict)
* `JavaString` — a Java `String` value

All beans accept `handle=0` when created from scratch; the writer assigns real
handles automatically during serialization.

```python
import javaobj.v3 as javaobj
from javaobj.constants import ClassDescFlags
from javaobj.v3.beans import (
    FieldType,
    JavaClassDesc,
    ClassDescType,
    JavaField,
    JavaInstance,
    JavaString,
)

# ── 1. Describe the Java class ────────────────────────────────────────────────
#
#  Java equivalent:
#
#    package com.example;
#    public class Point implements java.io.Serializable {
#        private static final long serialVersionUID = 1L;
#        public int x;
#        public int y;
#    }

field_x = JavaField(type=FieldType.INTEGER, name="x")
field_y = JavaField(type=FieldType.INTEGER, name="y")

point_cd = JavaClassDesc(
    handle=0,                              # assigned by the writer
    name="com.example.Point",
    serial_version_uid=1,
    desc_flags=ClassDescFlags.SC_SERIALIZABLE,
    fields=[field_x, field_y],
)

# ── 2. Create an instance ─────────────────────────────────────────────────────

point = JavaInstance(
    handle=0,
    classdesc=point_cd,
    field_data={
        point_cd: {
            field_x: 42,
            field_y: -7,
        }
    },
)

# ── 3. Serialize ──────────────────────────────────────────────────────────────

data = javaobj.dumps(point)

# ── 4. Round-trip check ───────────────────────────────────────────────────────

restored = javaobj.loads(data)
print(restored.get_field("x"))   # 42
print(restored.get_field("y"))   # -7
```

For object-type fields (e.g. a `String` attribute), use `FieldType.OBJECT`,
set `class_name` to the binary class name, and pass a `JavaString` as the
value:

```python
field_name = JavaField(
    type=FieldType.OBJECT,
    name="name",
    class_name="Ljava/lang/String;",   # binary name for java.lang.String
)

person_cd = JavaClassDesc(
    handle=0,
    name="com.example.Person",
    serial_version_uid=1,
    desc_flags=ClassDescFlags.SC_SERIALIZABLE,
    fields=[field_name, field_x],      # reuse field_x from above
)

alice = JavaInstance(
    handle=0,
    classdesc=person_cd,
    field_data={
        person_cd: {
            field_name: JavaString(handle=0, value="Alice"),
            field_x: 30,
        }
    },
)

data = javaobj.dumps(alice)
```

---

## Migration to V3

### From V1 to V3

| V1 | V3 |
|---|---|
| `import javaobj` | `import javaobj.v3 as javaobj` |
| `pobj.classdesc.name` | `pobj.classdesc.name` (unchanged) |
| `pobj.myField` (direct attribute) | `pobj.get_field("myField")` (preferred) or `pobj.myField` |
| `pobj._data` on arrays | `pobj.data` (public) |
| `javaobj.JavaObjectUnmarshaller` | removed — use `javaobj.v3.parser.JavaStreamParser` |
| `javaobj.JavaObjectMarshaller` | `javaobj.v3.dump` / `javaobj.v3.dumps` |
| Exceptions: bare `Exception` | Typed: `ParseError`, `UnexpectedOpcodeError`, … |

Shallow conversion helper (best-effort, for gradual migration):

```python
from javaobj.v3._compat import v1_to_v3
v3_obj = v1_to_v3(v1_obj)
```

### From V2 to V3

| V2 | V3 |
|---|---|
| `import javaobj.v2 as javaobj` | `import javaobj.v3 as javaobj` |
| `javaobj.load(fd)` | `javaobj.load(fd)` (same signature) |
| `javaobj.loads(data)` | `javaobj.loads(data)` (same signature) |
| `pobj.classdesc.name` | `pobj.classdesc.name` (unchanged) |
| `pobj.field_data[cd][field]` | `pobj.field_data[cd][field]` (unchanged) |
| `pobj.get_field("name")` | `pobj.get_field("name")` (unchanged) |
| `pobj.__getattr__` ambiguity silent | warns when field exists in multiple classes |
| `transformer._type_mapper` (private) | `transformer.handles(name)` (public) |
| `JavaArray.data` (`tuple` of ints for bytes) | `JavaArray.data` (`bytes` for `TYPE_BYTE`) |
| `BlockData` compared with `bytes` | `BlockData.__eq__(bytes)` still works |
| `use_numpy_arrays=True` (v2 option) | `use_numpy_arrays=True` (same) |
| No depth/size limits | `max_depth=500`, `max_array_size=100 MiB` |
| No typed exceptions | `ParseError`, `SecurityError`, … |

Shallow conversion helper (best-effort, for gradual migration):

```python
from javaobj.v3._compat import v2_to_v3
v3_obj = v2_to_v3(v2_obj)
```

> **Note:** `v3` requires **Python 3.12+**.
> For writing Java object streams on older Python versions, use `v1`.
