#!/usr/bin/python
# -- Content-Encoding: utf-8 --
"""
Tests for javaobj

See:
http://download.oracle.com/javase/6/docs/platform/serialization/spec/protocol.html

:authors: Volodymyr Buell, Thomas Calmant
:license: Apache License 2.0
:version: 0.6.1
:status: Alpha

..

    Copyright 2026 Thomas Calmant

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

# Print is used in tests
from __future__ import print_function

# Standard library
import logging
import os
import struct
import subprocess
import sys
import unittest
from io import BytesIO

# Prepare Python path to import javaobj
sys.path.insert(0, os.path.abspath(os.path.dirname(os.getcwd())))

import javaobj.v2 as javaobj

# Local
from javaobj.constants import ClassDescFlags, StreamConstants, TerminalCode, TypeCode
from javaobj.utils import BYTES_TYPE, UNICODE_TYPE, bytes_char, java_data_fd

try:
    import numpy
except ImportError:
    numpy = None

# ------------------------------------------------------------------------------

# Documentation strings format
__docformat__ = "restructuredtext en"

_logger = logging.getLogger("javaobj.tests")

# ------------------------------------------------------------------------------


# Custom writeObject parsing classes
class CustomWriterInstance(javaobj.beans.JavaInstance):
    def __init__(self):
        javaobj.beans.JavaInstance.__init__(self)

    def load_from_instance(self):
        """
        Updates the content of this instance
        from its parsed fields and annotations
        :return: True on success, False on error
        """
        if self.classdesc and self.classdesc in self.annotations:
            fields = ["int_not_in_fields"] + self.classdesc.fields_names
            raw_data = self.annotations[self.classdesc]
            int_not_in_fields = struct.unpack(">i", BytesIO(raw_data[0].data).read(4))[0]
            custom_obj = raw_data[1]
            values = [int_not_in_fields, custom_obj]
            self.field_data = dict(zip(fields, values))
            return True

        return False


class RandomChildInstance(javaobj.beans.JavaInstance):
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


class BaseTransformer(javaobj.transformers.ObjectTransformer):
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
        super(RandomChildTransformer, self).__init__({"RandomChild": RandomChildInstance})


class CustomWriterTransformer(BaseTransformer):
    def __init__(self):
        super(CustomWriterTransformer, self).__init__({"CustomWriter": CustomWriterInstance})


class JavaRandomTransformer(BaseTransformer):
    def __init__(self):
        super(JavaRandomTransformer, self).__init__()
        self.name = "java.util.Random"
        self.field_names = ["haveNextNextGaussian", "nextNextGaussian", "seed"]
        self.field_types = [
            javaobj.beans.FieldType.BOOLEAN,
            javaobj.beans.FieldType.DOUBLE,
            javaobj.beans.FieldType.LONG,
        ]

    def load_custom_writeObject(self, parser, reader, name):
        if name != self.name:
            return None

        fields = []
        values = []
        for f_name, f_type in zip(self.field_names, self.field_types):
            values.append(parser._read_field_value(f_type))
            fields.append(javaobj.beans.JavaField(f_type, f_name))

        class_desc = javaobj.beans.JavaClassDesc(javaobj.beans.ClassDescType.NORMALCLASS)
        class_desc.name = self.name
        class_desc.desc_flags = javaobj.beans.ClassDataType.EXTERNAL_CONTENTS
        class_desc.fields = fields
        class_desc.field_data = values
        return class_desc


# ------------------------------------------------------------------------------
# Hand-crafted byte-stream helpers (no Java toolchain required: the wire
# format is fully described by javaobj.constants).
# ------------------------------------------------------------------------------

STREAM_MAGIC = struct.pack(">HH", int(StreamConstants.STREAM_MAGIC), int(StreamConstants.STREAM_VERSION))


def _utf(s):
    encoded = s.encode("utf-8")
    return struct.pack(">H", len(encoded)) + encoded


def _tc(code):
    return struct.pack(">B", int(code))


def _classdesc_bytes(name, flags, field_bytes=b"", nb_fields=0, superclass=None):
    if superclass is None:
        superclass = _tc(TerminalCode.TC_NULL)
    return (
        _tc(TerminalCode.TC_CLASSDESC)
        + _utf(name)
        + struct.pack(">q", 0)  # serialVersionUID
        + struct.pack(">Bh", flags, nb_fields)
        + field_bytes
        + _tc(TerminalCode.TC_ENDBLOCKDATA)
        + superclass
    )


def _object_field(name, class_name_bytes):
    return struct.pack(">B", ord("L")) + _utf(name) + class_name_bytes


# ------------------------------------------------------------------------------


class TestJavaobjV2(unittest.TestCase):
    """
    Full test suite for javaobj V2 Parser
    """

    @classmethod
    def setUpClass(cls):
        """
        Calls Maven to compile & run Java classes that will generate serialized
        data
        """
        # Compute the java directory
        java_dir = os.path.join(os.path.dirname(__file__), "java")

        if not os.getenv("JAVAOBJ_NO_MAVEN"):
            # Run Maven and go back to the working folder
            cwd = os.getcwd()
            os.chdir(java_dir)
            subprocess.call("mvn test", shell=True)
            os.chdir(cwd)

    def read_file(self, filename, stream=False):
        """
        Reads the content of the given file in binary mode

        :param filename: Name of the file to read
        :param stream: If True, return the file stream
        :return: File content or stream
        """
        for subfolder in ("java", ""):
            found_file = os.path.join(os.path.dirname(__file__), subfolder, filename)
            if os.path.exists(found_file):
                break
        else:
            raise IOError("File not found: {0}".format(filename))

        if stream:
            return open(found_file, "rb")
        else:
            with open(found_file, "rb") as filep:
                return filep.read()

    def test_char_rw(self):
        """
        Reads testChar.ser and checks the serialization process
        """
        jobj = self.read_file("testChar.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char object: %s", pobj)
        self.assertEqual(pobj, b"\x00C")

    def test_chars_rw(self):
        """
        Reads testChars.ser and checks the serialization process
        """
        # Expected string as a UTF-16 string
        expected = "python-javaobj".encode("utf-16-be")

        jobj = self.read_file("testChars.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char objects: %s", pobj)
        self.assertEqual(pobj, expected)
        self.assertEqual(pobj, expected.decode("latin1"))

    def test_gzip_open(self):
        """
        Tests if the GZip auto-uncompress works
        """
        with java_data_fd(self.read_file("testChars.ser", stream=True)) as fd:
            base = fd.read()

        with java_data_fd(self.read_file("testChars.ser.gz", stream=True)) as fd:
            gzipped = fd.read()

        self.assertEqual(base, gzipped, "Uncompressed content doesn't match the original")

    def test_chars_gzip(self):
        """
        Reads testChars.ser.gz
        """
        # Expected string as a UTF-16 string
        expected = "python-javaobj".encode("utf-16-be")

        jobj = self.read_file("testChars.ser.gz")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char objects: %s", pobj)
        self.assertEqual(pobj, expected)
        self.assertEqual(pobj, expected.decode("latin1"))

    def test_double_rw(self):
        """
        Reads testDouble.ser and checks the serialization process
        """
        jobj = self.read_file("testDouble.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read double object: %s", pobj)

        self.assertEqual(pobj, b"\x7f\xef\xff\xff\xff\xff\xff\xff")

    def test_bytes_rw(self):
        """
        Reads testBytes.ser and checks the serialization process
        """
        jobj = self.read_file("testBytes.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read bytes: %s", pobj)

        self.assertEqual(pobj, b"HelloWorld")

    def test_class_with_byte_array_rw(self):
        """
        Tests handling of classes containing a Byte Array
        """
        jobj = self.read_file("testClassWithByteArray.ser")
        pobj = javaobj.loads(jobj)

        # j8spencer (Google, LLC) 2018-01-16:  It seems specific support for
        # byte arrays was added, but is a little out-of-step with the other
        # types in terms of style.  This UT was broken, since the "myArray"
        # member has the array stored as a tuple of ints (not a byte string)
        # in member called '_data.'  I've updated to pass the UTs.
        self.assertEqual(pobj.myArray._data, (1, 3, 7, 11))

    def test_boolean(self):
        """
        Reads testBoolean.ser and checks the serialization process
        """
        jobj = self.read_file("testBoolean.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read boolean object: %s", pobj)

        self.assertEqual(pobj, bytes_char(0))

    def test_byte(self):
        """
        Reads testByte.ser

        The result from javaobj is a single-character string.
        """
        jobj = self.read_file("testByte.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read Byte: %r", pobj)

        self.assertEqual(pobj, bytes_char(127))

    def test_fields(self):
        """
        Reads a serialized object and checks its fields
        """
        jobj = self.read_file("test_readFields.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read object: %s", pobj)

        self.assertEqual(pobj.aField1, "Gabba")
        self.assertEqual(pobj.aField2, None)

        classdesc = pobj.get_class()
        self.assertTrue(classdesc)
        self.assertEqual(classdesc.serialVersionUID, 0x7F0941F5)
        self.assertEqual(classdesc.name, "OneTest$SerializableTestHelper")

        _logger.debug("Class..........: %s", classdesc)
        _logger.debug(".. Flags.......: %s", classdesc.flags)
        _logger.debug(".. Fields Names: %s", classdesc.fields_names)
        _logger.debug(".. Fields Types: %s", classdesc.fields_types)

        self.assertEqual(len(classdesc.fields_names), 3)

    def test_class(self):
        """
        Reads the serialized String class
        """
        jobj = self.read_file("testClass.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read object: %s", pobj)
        self.assertEqual(pobj.name, "java.lang.String")

    # def test_swing_object(self):
    #     """
    #     Reads a serialized Swing component
    #     """
    #     jobj = self.read_file("testSwingObject.ser")
    #     pobj = javaobj.loads(jobj)
    #     _logger.debug("Read object: %s", pobj)
    #
    #     classdesc = pobj.get_class()
    #     _logger.debug("Class..........: %s", classdesc)
    #     _logger.debug(".. Fields Names: %s", classdesc.fields_names)
    #     _logger.debug(".. Fields Types: %s", classdesc.fields_types)

    def test_super(self):
        """
        Tests basic class inheritance handling
        """
        jobj = self.read_file("objSuper.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        classdesc = pobj.get_class()
        _logger.debug(classdesc)
        _logger.debug(classdesc.fields_names)
        _logger.debug(classdesc.fields_types)

        self.assertEqual(pobj.childString, "Child!!")
        self.assertEqual(pobj.bool, True)
        self.assertEqual(pobj.integer, -1)
        self.assertEqual(pobj.superString, "Super!!")

    def test_arrays(self):
        """
        Tests handling of Java arrays
        """
        jobj = self.read_file("objArrays.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        classdesc = pobj.get_class()
        _logger.debug(classdesc)
        _logger.debug(classdesc.fields_names)
        _logger.debug(classdesc.fields_types)

        # public String[] stringArr = {"1", "2", "3"};
        # public int[] integerArr = {1,2,3};
        # public boolean[] boolArr = {true, false, true};
        # public TestConcrete[] concreteArr = {new TestConcrete(),
        #                                      new TestConcrete()};

        _logger.debug(pobj.stringArr)
        _logger.debug(pobj.integerArr)
        _logger.debug(pobj.boolArr)
        _logger.debug(pobj.concreteArr)

    def test_japan(self):
        """
        Tests the UTF encoding handling with Japanese characters
        """
        # Japan.ser contains a string using wide characters: the name of the
        # state from Japan (according to wikipedia)
        jobj = self.read_file("testJapan.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)
        # Compare the UTF-8 encoded version of the name
        self.assertEqual(pobj, b"\xe6\x97\xa5\xe6\x9c\xac\xe5\x9b\xbd".decode("utf-8"))

    def test_char_array(self):
        """
        Tests the loading of a wide-char array
        """
        jobj = self.read_file("testCharArray.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)
        # Compare by code points to avoid Python 2/3 string literal ambiguity
        # (ruff strips u"" prefixes; \u-escapes in plain str are literal in Py2)
        expected_codepoints = [0x0000, 0xD800, 0x0001, 0xDC00, 0x0002, 0xFFFF, 0x0003]
        self.assertEqual(len(pobj), len(expected_codepoints))
        for actual, cp in zip(pobj, expected_codepoints):
            self.assertEqual(ord(actual), cp)

    def test_2d_array(self):
        """
        Tests the handling of a 2D array
        """
        jobj = self.read_file("test2DArray.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)
        self.assertEqual(
            pobj,
            [
                [1, 2, 3],
                [4, 5, 6],
            ],
        )

    def test_class_array(self):
        """
        Tests the handling of an array of Class objects
        """
        jobj = self.read_file("testClassArray.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)
        self.assertEqual(pobj[0].name, "java.lang.Integer")
        self.assertEqual(pobj[1].name, "java.io.ObjectOutputStream")
        self.assertEqual(pobj[2].name, "java.lang.Exception")

    def test_enums(self):
        """
        Tests the handling of "enum" types
        """
        jobj = self.read_file("objEnums.ser")
        pobj = javaobj.loads(jobj)

        classdesc = pobj.get_class()
        _logger.debug("classdesc: {0}".format(classdesc))
        _logger.debug("fields_names: {0}".format(classdesc.fields_names))
        _logger.debug("fields_types: {0}".format(classdesc.fields_types))

        self.assertEqual(classdesc.name, "ClassWithEnum")
        self.assertEqual(pobj.color.classdesc.name, "Color")
        self.assertEqual(pobj.color.constant, "GREEN")

        for color, intended in zip(pobj.colors, ("GREEN", "BLUE", "RED")):
            _logger.debug("color: {0} - {1}".format(color, type(color)))
            self.assertEqual(color.classdesc.name, "Color")
            self.assertEqual(color.constant, intended)

    def test_sets(self):
        """
        Tests handling of HashSet and TreeSet
        """
        for filename in (
            "testHashSet.ser",
            "testTreeSet.ser",
            "testLinkedHashSet.ser",
        ):
            _logger.debug("Loading file: %s", filename)
            jobj = self.read_file(filename)
            pobj = javaobj.loads(jobj)
            _logger.debug(pobj)
            self.assertIsInstance(pobj, set)
            self.assertSetEqual({i.value for i in pobj}, {1, 2, 42})

    def test_times(self):
        """
        Tests the handling of java.time classes
        """
        jobj = self.read_file("testTime.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        # First one is a duration of 10s
        duration = pobj[0]
        self.assertEqual(duration.second, 10)

        # Check types
        self.assertIsInstance(pobj, javaobj.beans.JavaArray)
        for obj in pobj:
            self.assertIsInstance(obj, javaobj.transformers.JavaTime)

    # def test_exception(self):
    #     jobj = self.read_file("objException.ser")
    #     pobj = javaobj.loads(jobj)
    #     _logger.debug(pobj)
    #
    #     classdesc = pobj.get_class()
    #     _logger.debug(classdesc)
    #     _logger.debug(classdesc.fields_names)
    #     _logger.debug(classdesc.fields_types)
    #
    #     # TODO: add some tests
    #     self.assertEqual(classdesc.name, "MyExceptionWhenDumping")

    def test_sun_example(self):
        content = javaobj.load(self.read_file("sunExample.ser", stream=True))

        pobj = content[0]
        self.assertEqual(pobj.value, 17)
        self.assertTrue(pobj.next)

        pobj = content[1]
        self.assertEqual(pobj.value, 19)
        self.assertFalse(pobj.next)

    def test_collections(self):
        """
        Tests the handling of ArrayList, LinkedList and HashMap
        """
        jobj = self.read_file("objCollections.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        _logger.debug("arrayList: %s", pobj.arrayList)
        self.assertTrue(isinstance(pobj.arrayList, list))
        _logger.debug("hashMap: %s", pobj.hashMap)
        self.assertTrue(isinstance(pobj.hashMap, dict))
        _logger.debug("linkedList: %s", pobj.linkedList)
        self.assertTrue(isinstance(pobj.linkedList, list))

        # FIXME: referencing problems with the collection class

    def test_linked_hash_map(self):
        """
        Tests the handling of LinkedHashMap (issue #30)

        The entries of a LinkedHashMap are written in the block data of the
        HashMap it extends, hence found in the annotations of that parent.
        """
        pobj = javaobj.loads(self.read_file("testBareLinkedHashMap.ser"))
        self.assertEqual(dict(pobj), {"a": "1", "b": "2"})

        pobj = javaobj.loads(self.read_file("testLinkedHashMap.ser"))
        self.assertEqual(pobj.name, "holder")
        self.assertEqual(dict(pobj.settings), {"first": "1", "second": "2"})
        self.assertEqual(pobj.port, 443)

    def test_shared_array(self):
        """
        Tests the reference to an array stored in two fields (issue #62)

        The array is written once and referenced the second time: the
        reference must be resolved to the array, and not read as a class
        description.
        """
        pobj = javaobj.loads(self.read_file("testSharedArray.ser"))

        self.assertEqual(list(pobj.first), [1, 2, 3])
        self.assertEqual(list(pobj.second), [1, 2, 3])
        self.assertEqual(list(pobj.strings), ["a", "b"])
        self.assertEqual(list(pobj.sameStrings), ["a", "b"])

        # Both fields must give the very same array
        self.assertIs(pobj.first, pobj.second)
        self.assertIs(pobj.strings, pobj.sameStrings)

        # Field written after the shared arrays: a wrong value here means
        # the stream has been desynchronized
        self.assertEqual(pobj.marker, 443)

    def test_jceks_issue_5(self):
        """
        Tests the handling of JCEKS issue #5
        """
        jobj = self.read_file("jceks_issue_5.ser")
        pobj = javaobj.loads(jobj)
        _logger.info(pobj)

    def test_qistoph_pr_27(self):
        """
        Tests support for Bool, Integer, Long classes (PR #27)
        """
        # Load the basic map
        jobj = self.read_file("testBoolIntLong.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        # Basic checking
        self.assertEqual(pobj["key1"], "value1")
        self.assertEqual(pobj["key2"], "value2")
        self.assertEqual(pobj["int"], 9)
        self.assertEqual(pobj["int2"], 10)
        self.assertEqual(pobj["bool"], True)
        self.assertEqual(pobj["bool2"], True)

        # Load the parent map
        jobj2 = self.read_file("testBoolIntLong-2.ser")
        pobj2 = javaobj.loads(jobj2)
        _logger.debug(pobj2)

        parent_map = pobj2["subMap"]
        for key, value in pobj.items():
            self.assertEqual(parent_map[key], value)

    def test_writeObject(self):
        """
        Tests support for custom writeObject (PR #38)
        """

        ser = self.read_file("testCustomWriteObject.ser")
        transformers = [
            CustomWriterTransformer(),
            RandomChildTransformer(),
            JavaRandomTransformer(),
        ]
        pobj = javaobj.loads(ser, *transformers)

        self.assertEqual(isinstance(pobj, CustomWriterInstance), True)
        self.assertEqual(
            isinstance(pobj.field_data["custom_obj"], RandomChildInstance),
            True,
        )

        parent_data = pobj.field_data
        child_data = parent_data["custom_obj"].field_data
        super_data = parent_data["custom_obj"].annotations
        expected = {
            "int_not_in_fields": 0,
            "custom_obj": {
                "field_data": {"doub": 4.5, "num": 1},
                "annotations": {
                    "haveNextNextGaussian": False,
                    "nextNextGaussian": 0.0,
                    "seed": 25214903879,
                },
            },
        }

        self.assertEqual(expected["int_not_in_fields"], parent_data["int_not_in_fields"])
        self.assertEqual(expected["custom_obj"]["field_data"], child_data)
        self.assertEqual(expected["custom_obj"]["annotations"], super_data)

    def test_instance_dump(self):
        """
        Smoke test for JavaInstance.dump() (debug string representation)
        """
        jobj = self.read_file("objSuper.ser")
        pobj = javaobj.loads(jobj)
        text = pobj.dump()
        self.assertIsInstance(text, (BYTES_TYPE, UNICODE_TYPE))
        self.assertIn(pobj.get_class().name, text)

    def test_array_dump(self):
        """
        Smoke test for JavaArray.dump() (debug string representation)
        """
        jobj = self.read_file("test2DArray.ser")
        pobj = javaobj.loads(jobj)
        text = pobj.dump()
        self.assertIsInstance(text, (BYTES_TYPE, UNICODE_TYPE))
        self.assertIn("array", text)

    def test_parser_dump(self):
        """
        Smoke test for JavaStreamParser.dump()
        """
        parser = javaobj.core.JavaStreamParser(
            self.read_file("objSuper.ser", stream=True),
            [javaobj.transformers.DefaultObjectTransformer()],
        )
        content = parser.run()
        text = parser.dump(content)
        self.assertIsInstance(text, (BYTES_TYPE, UNICODE_TYPE))
        self.assertIn("BEGIN stream content output", text)


# ------------------------------------------------------------------------------
# Malformed-stream / defensive-branch tests
# ------------------------------------------------------------------------------


class TestTransformersArgument(unittest.TestCase):
    """
    Tests the check of the transformers given to load() and loads()
    (issue #54)
    """

    def test_transformer_class_rejected(self):
        """
        Giving a transformer class instead of an instance must be reported
        clearly, and not fail later in the parser
        """
        data = STREAM_MAGIC + _tc(TerminalCode.TC_NULL)

        for method, argument in (
            (javaobj.loads, data),
            (javaobj.load, BytesIO(data)),
        ):
            with self.assertRaises(TypeError) as context:
                method(argument, RandomChildTransformer)

            message = str(context.exception)
            self.assertIn("instances", message)
            self.assertIn("RandomChildTransformer", message)

    def test_transformer_instance_accepted(self):
        """
        An instance is valid, whether it inherits from ObjectTransformer or
        not: those transformers are duck-typed
        """
        data = STREAM_MAGIC + _tc(TerminalCode.TC_NULL)

        class DuckTransformer(object):
            def create_instance(self, classdesc):
                return None

        self.assertIsNone(javaobj.loads(data, RandomChildTransformer()))
        self.assertIsNone(javaobj.loads(data, DuckTransformer()))


class TestMalformedStreams(unittest.TestCase):
    """
    Feeds hand-crafted, syntactically-invalid streams to the v2 parser to
    exercise its defensive ``ValueError`` guard clauses. No Java toolchain
    is needed: the wire format only requires following javaobj.constants
    byte-for-byte.
    """

    def test_bad_magic(self):
        with self.assertRaises(ValueError):
            javaobj.loads(b"\x00\x00\x00\x05")

    def test_bad_version(self):
        with self.assertRaises(ValueError):
            javaobj.loads(struct.pack(">HH", int(StreamConstants.STREAM_MAGIC), 0x99))

    def test_unknown_top_level_opcode(self):
        data = STREAM_MAGIC + b"\x01"
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_unexpected_blockdata_in_exception(self):
        data = STREAM_MAGIC + _tc(TerminalCode.TC_EXCEPTION) + _tc(TerminalCode.TC_BLOCKDATA)
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_null_class_description(self):
        """
        An object, a class and an array all require a class description:
        a null one must be reported, and not crash on a missing attribute
        """
        for type_code in (
            TerminalCode.TC_OBJECT,
            TerminalCode.TC_CLASS,
            TerminalCode.TC_ARRAY,
        ):
            data = STREAM_MAGIC + _tc(type_code) + _tc(TerminalCode.TC_NULL)
            with self.assertRaises(ValueError) as context:
                javaobj.loads(data)

            self.assertIn("class description", str(context.exception))

    def test_invalid_field_count(self):
        cd = _classdesc_bytes("Foo", int(ClassDescFlags.SC_SERIALIZABLE), nb_fields=-1)
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + cd
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_invalid_field_type_char(self):
        bad_field = struct.pack(">B", 0xFF) + _utf("x")
        cd = _classdesc_bytes("Foo", int(ClassDescFlags.SC_SERIALIZABLE), field_bytes=bad_field, nb_fields=1)
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + cd
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_classdesc_reference_not_classdesc(self):
        data = (
            STREAM_MAGIC
            + _tc(TerminalCode.TC_STRING)
            + _utf("hi")
            + _tc(TerminalCode.TC_ARRAY)
            + _tc(TerminalCode.TC_REFERENCE)
            + struct.pack(">i", int(StreamConstants.BASE_REFERENCE_IDX))
        )
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_string_reference_not_string(self):
        cd1 = _classdesc_bytes("A", int(ClassDescFlags.SC_SERIALIZABLE))
        field = _object_field(
            "x",
            _tc(TerminalCode.TC_REFERENCE) + struct.pack(">i", int(StreamConstants.BASE_REFERENCE_IDX)),
        )
        cd2 = _classdesc_bytes("B", int(ClassDescFlags.SC_SERIALIZABLE), field_bytes=field, nb_fields=1)
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + cd1 + _tc(TerminalCode.TC_CLASS) + cd2
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_classdesc_invalid_starter(self):
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + b"\x00"
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_custom_readobject_not_processed(self):
        flags = int(ClassDescFlags.SC_SERIALIZABLE) | int(ClassDescFlags.SC_WRITE_METHOD)
        cd = _classdesc_bytes("XYZ", flags)
        data = STREAM_MAGIC + _tc(TerminalCode.TC_OBJECT) + cd + b"\x00"
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_object_annotation_no_transformer(self):
        # v2 derives OBJECT_ANNOTATION from SC_EXTERNALIZABLE + SC_WRITE_METHOD
        flags = int(ClassDescFlags.SC_EXTERNALIZABLE) | int(ClassDescFlags.SC_WRITE_METHOD)
        cd = _classdesc_bytes("Foo", flags)
        data = STREAM_MAGIC + _tc(TerminalCode.TC_OBJECT) + cd
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_array_field_invalid_subtype(self):
        field = _object_field("arr", _tc(TerminalCode.TC_STRING) + _utf("[I"))
        # Field descriptor byte must be TYPE_ARRAY ('['), not TYPE_OBJECT:
        field = struct.pack(">B", ord("[")) + field[1:]
        cd = _classdesc_bytes("Foo", int(ClassDescFlags.SC_SERIALIZABLE), field_bytes=field, nb_fields=1)
        data = STREAM_MAGIC + _tc(TerminalCode.TC_OBJECT) + cd + b"\x00"
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_enum_description_null(self):
        data = STREAM_MAGIC + _tc(TerminalCode.TC_ENUM) + _tc(TerminalCode.TC_NULL)
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_array_invalid_name(self):
        cd = _classdesc_bytes("X", int(ClassDescFlags.SC_SERIALIZABLE))
        data = STREAM_MAGIC + _tc(TerminalCode.TC_ARRAY) + cd
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_array_invalid_size(self):
        cd = _classdesc_bytes("[B", int(ClassDescFlags.SC_SERIALIZABLE))
        data = STREAM_MAGIC + _tc(TerminalCode.TC_ARRAY) + cd + struct.pack(">i", -1)
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_invalid_handle_reference(self):
        data = STREAM_MAGIC + _tc(TerminalCode.TC_REFERENCE) + struct.pack(">i", 0x7E1234)
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_reset_during_exception(self):
        data = STREAM_MAGIC + _tc(TerminalCode.TC_EXCEPTION) + _tc(TerminalCode.TC_RESET)
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_null_exception_object(self):
        data = STREAM_MAGIC + _tc(TerminalCode.TC_EXCEPTION) + _tc(TerminalCode.TC_NULL)
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_exception_object_not_instance(self):
        data = STREAM_MAGIC + _tc(TerminalCode.TC_EXCEPTION) + _tc(TerminalCode.TC_STRING) + _utf("hello")
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_invalid_blockdatalong_size(self):
        data = STREAM_MAGIC + _tc(TerminalCode.TC_BLOCKDATALONG) + struct.pack(">i", -1)
        with self.assertRaises(ValueError):
            javaobj.loads(data)

    def test_duplicate_handle(self):
        # White-box: handles are always freshly allocated by the parser
        # itself, so duplication can only be triggered via the internal API.
        parser = javaobj.core.JavaStreamParser(BytesIO(b""), [javaobj.transformers.DefaultObjectTransformer()])
        handle = parser._new_handle()
        parser._set_handle(handle, None)
        with self.assertRaises(ValueError):
            parser._set_handle(handle, None)


# ------------------------------------------------------------------------------
# JavaClassDesc.validate() / field-access tests
# ------------------------------------------------------------------------------


class TestParserInterface(unittest.TestCase):
    """
    Tests the IJavaStreamParser interface, which a transformer may be given
    """

    def test_methods_are_abstract(self):
        """
        Every method of the interface must be implemented by the parser:
        none of them must silently return None
        """
        parser = javaobj.api.IJavaStreamParser()

        self.assertRaises(NotImplementedError, parser.run)
        self.assertRaises(NotImplementedError, parser.dump, [])
        self.assertRaises(
            NotImplementedError, parser._read_content, 0, False, None
        )


class TestBeansValidation(unittest.TestCase):
    """Direct unit tests for JavaClassDesc.validate() and field access."""

    @staticmethod
    def _cd(flags, fields=None, interfaces=None, enum_constants=None):
        cd = javaobj.beans.JavaClassDesc(javaobj.beans.ClassDescType.NORMALCLASS)
        cd.desc_flags = flags
        cd.fields = fields or []
        cd.interfaces = interfaces or []
        cd.enum_constants = set(enum_constants or [])
        return cd

    def test_valid_serializable(self):
        cd = self._cd(int(ClassDescFlags.SC_SERIALIZABLE))
        cd.validate()  # must not raise

    def test_non_serializable_with_fields(self):
        field = javaobj.beans.JavaField(javaobj.beans.FieldType.INTEGER, "x")
        cd = self._cd(0, fields=[field])
        with self.assertRaises(ValueError):
            cd.validate()

    def test_serializable_and_externalizable(self):
        flags = int(ClassDescFlags.SC_SERIALIZABLE) | int(ClassDescFlags.SC_EXTERNALIZABLE)
        cd = self._cd(flags)
        with self.assertRaises(ValueError):
            cd.validate()

    def test_enum_with_fields(self):
        flags = int(ClassDescFlags.SC_SERIALIZABLE) | int(ClassDescFlags.SC_ENUM)
        field = javaobj.beans.JavaField(javaobj.beans.FieldType.INTEGER, "x")
        cd = self._cd(flags, fields=[field])
        with self.assertRaises(ValueError):
            cd.validate()

    def test_enum_with_interfaces(self):
        flags = int(ClassDescFlags.SC_SERIALIZABLE) | int(ClassDescFlags.SC_ENUM)
        cd = self._cd(flags, interfaces=["java.lang.Runnable"])
        with self.assertRaises(ValueError):
            cd.validate()

    def test_non_enum_with_enum_constants(self):
        cd = self._cd(int(ClassDescFlags.SC_SERIALIZABLE), enum_constants=["RED"])
        with self.assertRaises(ValueError):
            cd.validate()

    def test_data_type_invalid_flags_raises(self):
        cd = self._cd(0)
        with self.assertRaises(ValueError):
            _ = cd.data_type

    def test_getattr_unknown_raises(self):
        instance = javaobj.beans.JavaInstance()
        with self.assertRaises(AttributeError):
            _ = instance.unknown_attribute

    def test_object_field_invalid_class_name(self):
        with self.assertRaises(ValueError):
            javaobj.beans.JavaField(javaobj.beans.FieldType.OBJECT, "x", class_name=type("S", (), {"value": ""})())


# ------------------------------------------------------------------------------
# NumpyArrayTransformer
# ------------------------------------------------------------------------------


@unittest.skipIf(numpy is None, "numpy is not installed")
class TestNumpyArrayTransformerV2(unittest.TestCase):
    """Tests for the optional numpy-backed array transformer (v2)."""

    @staticmethod
    def _fixture_path(filename):
        for subfolder in ("java", ""):
            found_file = os.path.join(os.path.dirname(__file__), subfolder, filename)
            if os.path.exists(found_file):
                return found_file
        raise IOError("File not found: {0}".format(filename))

    def test_use_numpy_arrays(self):
        with open(self._fixture_path("objArrays.ser"), "rb") as f:
            pobj = javaobj.load(f, use_numpy_arrays=True)

        self.assertIsInstance(pobj, javaobj.beans.JavaInstance)
        arr = pobj.integerArr
        self.assertIsInstance(arr, javaobj.beans.JavaArray)
        self.assertIsInstance(arr.data, numpy.ndarray)
        self.assertEqual(arr.data.dtype, numpy.dtype(">i"))

    def test_unhandled_type_returns_none(self):
        from javaobj.v2.stream import DataStreamReader
        from javaobj.v2.transformers import NumpyArrayTransformer

        transformer = NumpyArrayTransformer()
        reader = DataStreamReader(BytesIO(b""))
        result = transformer.load_array(reader, TypeCode.TYPE_OBJECT, 0)
        self.assertIsNone(result)


# ------------------------------------------------------------------------------
# Direct transformer unit tests (white-box: pure-Python logic, no stream
# parsing needed for most branches).
# ------------------------------------------------------------------------------


class TestTransformersDirect(unittest.TestCase):
    """Direct unit tests for javaobj.v2.transformers branch coverage."""

    @staticmethod
    def _cd(name):
        cd = javaobj.beans.JavaClassDesc(javaobj.beans.ClassDescType.NORMALCLASS)
        cd.name = name
        return cd

    def test_java_list_not_found(self):
        jl = javaobj.transformers.JavaList()
        jl.annotations = {self._cd("other"): []}
        self.assertFalse(jl.load_from_instance())

    def test_java_map_not_found(self):
        jm = javaobj.transformers.JavaMap()
        jm.annotations = {self._cd("other"): []}
        self.assertFalse(jm.load_from_instance())

    def test_java_set_not_found(self):
        js = javaobj.transformers.JavaSet()
        js.annotations = {self._cd("other"): []}
        self.assertFalse(js.load_from_instance())

    def test_java_tree_set_not_found(self):
        jts = javaobj.transformers.JavaTreeSet()
        jts.annotations = {self._cd("other"): []}
        self.assertFalse(jts.load_from_instance())

    def test_java_primitive_class_not_found(self):
        jb = javaobj.transformers.JavaBool()
        jb.field_data = {}
        self.assertFalse(jb.load_from_instance())

    def test_java_primitive_class_dunder(self):
        ji = javaobj.transformers.JavaInt()
        ji.value = 5
        self.assertEqual(int(ji), 5)
        self.assertEqual(hash(ji), hash(5))
        self.assertLess(ji, 6)
        self.assertEqual(ji, 5)

        jb = javaobj.transformers.JavaBool()
        jb.value = True
        self.assertTrue(bool(jb))

    def test_linked_hash_map_positive(self):
        from javaobj.v2.stream import DataStreamReader

        data = (
            struct.pack(">ii", 16, 1)
            + _tc(TerminalCode.TC_NULL)
            + _tc(TerminalCode.TC_NULL)
            + _tc(TerminalCode.TC_ENDBLOCKDATA)
            + b"\x00"
        )
        fd = BytesIO(data)
        reader = DataStreamReader(fd)
        parser = javaobj.core.JavaStreamParser(fd, [javaobj.transformers.DefaultObjectTransformer()])
        lhm = javaobj.transformers.JavaLinkedHashMap()
        self.assertTrue(lhm.load_from_blockdata(parser, reader))
        self.assertEqual(dict(lhm), {None: None})

    def test_linked_hash_map_bad_endblock(self):
        from javaobj.v2.stream import DataStreamReader

        data = struct.pack(">ii", 16, 0) + b"\x00"
        reader = DataStreamReader(BytesIO(data))
        with self.assertRaises(ValueError):
            javaobj.transformers.JavaLinkedHashMap().load_from_blockdata(None, reader)

    def test_linked_hash_map_bad_trailing_byte(self):
        from javaobj.v2.stream import DataStreamReader

        data = struct.pack(">ii", 16, 0) + _tc(TerminalCode.TC_ENDBLOCKDATA) + b"\x01"
        reader = DataStreamReader(BytesIO(data))
        with self.assertRaises(ValueError):
            javaobj.transformers.JavaLinkedHashMap().load_from_blockdata(None, reader)

    def test_java_time_not_found(self):
        jt = javaobj.transformers.JavaTime()
        jt.annotations = {self._cd("other"): []}
        self.assertFalse(jt.load_from_instance())

    def test_java_time_requires_blockdata(self):
        jt = javaobj.transformers.JavaTime()
        jt.annotations = {self._cd("java.time.Ser"): ["not blockdata"]}
        with self.assertRaises(ValueError):
            jt.load_from_instance()

    def test_java_time_unhandled_type(self):
        jt = javaobj.transformers.JavaTime()
        jt.annotations = {self._cd("java.time.Ser"): [javaobj.beans.BlockData(struct.pack(">B", 99))]}
        self.assertTrue(jt.load_from_instance())  # logs an error, does not raise

    def test_java_time_local_time_branches(self):
        jt = javaobj.transformers.JavaTime()
        jt.do_local_time(struct.pack(">b", -5))
        self.assertEqual(jt.hour, 4)

        jt = javaobj.transformers.JavaTime()
        jt.do_local_time(struct.pack(">bb", 5, -3))
        self.assertEqual(jt.minute, 2)

        jt = javaobj.transformers.JavaTime()
        jt.do_local_time(struct.pack(">bbb", 5, 3, -2))
        self.assertEqual(jt.second, 1)

        jt = javaobj.transformers.JavaTime()
        jt.do_local_time(struct.pack(">bbbi", 5, 3, 2, 12345))
        self.assertEqual(jt.nano, 12345)

    def test_java_time_zone_offset_large(self):
        jt = javaobj.transformers.JavaTime()
        jt.do_zone_offset(struct.pack(">bi", 127, 999999))
        self.assertEqual(jt.offset, 999999)

    def test_java_time_load_from_blockdata(self):
        jt = javaobj.transformers.JavaTime()
        self.assertTrue(jt.load_from_blockdata(None, None))

    def test_java_time_remaining_do_methods(self):
        jt = javaobj.transformers.JavaTime()
        jt.do_offset_time(struct.pack(">b", -5) + struct.pack(">bi", 127, 111))
        self.assertEqual(jt.offset, 111)

        jt = javaobj.transformers.JavaTime()
        jt.do_offset_date_time(struct.pack(">ibb", 2024, 6, 1) + struct.pack(">b", -5) + struct.pack(">b", 4))
        self.assertEqual(jt.year, 2024)

        jt = javaobj.transformers.JavaTime()
        jt.do_year(struct.pack(">i", 2024))
        self.assertEqual(jt.year, 2024)

        jt = javaobj.transformers.JavaTime()
        jt.do_year_month(struct.pack(">ib", 2024, 6))
        self.assertEqual((jt.year, jt.month), (2024, 6))

        jt = javaobj.transformers.JavaTime()
        jt.do_month_day(struct.pack(">bb", 6, 15))
        self.assertEqual((jt.month, jt.day), (6, 15))

        jt = javaobj.transformers.JavaTime()
        jt.do_period(struct.pack(">iii", 1, 2, 3))
        self.assertEqual((jt.year, jt.month, jt.day), (1, 2, 3))


# ------------------------------------------------------------------------------


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Run tests
    unittest.main()
