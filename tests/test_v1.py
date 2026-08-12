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

# Local
import javaobj.v1 as javaobj
from javaobj.constants import ClassDescFlags, StreamConstants, TerminalCode, TypeCode
from javaobj.utils import hexdump, java_data_fd

# Prepare Python path to import javaobj
sys.path.insert(0, os.path.abspath(os.path.dirname(os.getcwd())))

try:
    import numpy
except ImportError:
    numpy = None

# ------------------------------------------------------------------------------

# Documentation strings format
__docformat__ = "restructuredtext en"

_logger = logging.getLogger("javaobj.tests")

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


def _classdesc_bytes(name, flags, field_bytes=b"", nb_fields=0, class_annotation=None, superclass=None):
    """
    Builds a TC_CLASSDESC record body, including its own leading opcode
    byte (the caller is expected to have already written the opcode of
    the object/class/array/enum that references this class description).
    """
    if class_annotation is None:
        class_annotation = _tc(TerminalCode.TC_ENDBLOCKDATA)
    if superclass is None:
        superclass = _tc(TerminalCode.TC_NULL)
    return (
        _tc(TerminalCode.TC_CLASSDESC)
        + _utf(name)
        + struct.pack(">qB", 0, flags)
        + struct.pack(">H", nb_fields)
        + field_bytes
        + class_annotation
        + superclass
    )


# ------------------------------------------------------------------------------


class TestJavaobjV1(unittest.TestCase):
    """
    Full test suite for javaobj V1 parser
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

    def _try_marshalling(self, original_stream, original_object):
        """
        Tries to marshall an object and compares it to the original stream
        """
        _logger.debug("Try Marshalling")
        marshalled_stream = javaobj.dumps(original_object)
        # Reloading the new dump allows to compare the decoding sequence
        try:
            javaobj.loads(marshalled_stream)
            self.assertEqual(original_stream, marshalled_stream)
        except Exception:
            print("-" * 80)
            print("=" * 30, "Original", "=" * 30)
            print(hexdump(original_stream))
            print("*" * 30, "Marshalled", "*" * 30)
            print(hexdump(marshalled_stream))
            print("-" * 80)
            raise

    def test_char_rw(self):
        """
        Reads testChar.ser and checks the serialization process
        """
        jobj = self.read_file("testChar.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char object: %s", pobj)
        self.assertEqual(pobj, "\x00C")
        self._try_marshalling(jobj, pobj)

    def test_chars_rw(self):
        """
        Reads testChars.ser and checks the serialization process
        """
        # Expected string as a UTF-16 string
        expected = "python-javaobj".encode("utf-16-be").decode("latin1")

        jobj = self.read_file("testChars.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char objects: %s", pobj)
        self.assertEqual(pobj, expected)
        self._try_marshalling(jobj, pobj)

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
        expected = "python-javaobj".encode("utf-16-be").decode("latin1")

        jobj = self.read_file("testChars.ser.gz")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char objects: %s", pobj)
        self.assertEqual(pobj, expected)

    def test_double_rw(self):
        """
        Reads testDouble.ser and checks the serialization process
        """
        jobj = self.read_file("testDouble.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read double object: %s", pobj)

        self.assertEqual(pobj, "\x7f\xef\xff\xff\xff\xff\xff\xff")
        self._try_marshalling(jobj, pobj)

    def test_bytes_rw(self):
        """
        Reads testBytes.ser and checks the serialization process
        """
        jobj = self.read_file("testBytes.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read bytes: %s", pobj)

        self.assertEqual(pobj, "HelloWorld")
        self._try_marshalling(jobj, pobj)

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
        # in memeber called '_data.'  I've updated to pass the UTs.
        self.assertEqual(pobj.myArray._data, (1, 3, 7, 11))
        self._try_marshalling(jobj, pobj)

    def test_boolean(self):
        """
        Reads testBoolean.ser and checks the serialization process
        """
        jobj = self.read_file("testBoolean.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read boolean object: %s", pobj)

        self.assertEqual(pobj, chr(0))
        self._try_marshalling(jobj, pobj)

    def test_byte(self):
        """
        Reads testByte.ser

        The result from javaobj is a single-character string.
        """
        jobj = self.read_file("testByte.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read Byte: %r", pobj)

        self.assertEqual(pobj, chr(127))
        self._try_marshalling(jobj, pobj)

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
        self._try_marshalling(jobj, pobj)

    def test_class(self):
        """
        Reads the serialized String class
        """
        jobj = self.read_file("testClass.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read object: %s", pobj)
        self.assertEqual(pobj.name, "java.lang.String")
        self._try_marshalling(jobj, pobj)

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

        self._try_marshalling(jobj, pobj)

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

        self._try_marshalling(jobj, pobj)

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
        self._try_marshalling(jobj, pobj)

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
        self._try_marshalling(jobj, pobj)

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

    def test_enums(self):
        """
        Tests the handling of "enum" types
        """
        jobj = self.read_file("objEnums.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        classdesc = pobj.get_class()
        _logger.debug(classdesc)
        _logger.debug(classdesc.fields_names)
        _logger.debug(classdesc.fields_types)

        self.assertEqual(classdesc.name, "ClassWithEnum")
        self.assertEqual(pobj.color.classdesc.name, "Color")
        self.assertEqual(pobj.color.constant, "GREEN")

        for color, intended in zip(pobj.colors, ("GREEN", "BLUE", "RED")):
            self.assertEqual(color.classdesc.name, "Color")
            self.assertEqual(color.constant, intended)

            # self._try_marshalling(jobj, pobj)

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
            self.assertIsInstance(obj, javaobj.DefaultObjectTransformer.JavaTime)

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
        marshaller = javaobj.JavaObjectUnmarshaller(self.read_file("sunExample.ser", stream=True))
        pobj = marshaller.readObject()

        self.assertEqual(pobj.value, 17)
        self.assertTrue(pobj.next)

        pobj = marshaller.readObject()

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
        # self._try_marshalling(jobj, pobj)

    def test_linked_hash_map(self):
        """
        Tests the handling of LinkedHashMap (issue #30)

        The entries of a LinkedHashMap are written in the block data of the
        HashMap it extends. Reading that block data twice used to consume
        the fields written after the map, and to fail on the way.
        """
        # A LinkedHashMap written on its own
        pobj = javaobj.loads(self.read_file("testBareLinkedHashMap.ser"))
        self.assertEqual(dict(pobj), {"a": "1", "b": "2"})

        # A LinkedHashMap nested in an object
        pobj = javaobj.loads(self.read_file("testLinkedHashMap.ser"))
        self.assertEqual(pobj.name, "holder")
        self.assertEqual(dict(pobj.settings), {"first": "1", "second": "2"})
        # The field written after the map: it was misread before the fix
        self.assertEqual(pobj.port, 443)

    def test_jceks_issue_5(self):
        """
        Tests the handling of JCEKS issue #5
        """
        jobj = self.read_file("jceks_issue_5.ser")
        pobj = javaobj.loads(jobj)
        _logger.info(pobj)
        # self._try_marshalling(jobj, pobj)

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

    def test_read_custom(self):
        """
        Tests to verify that the super-class is properly read when a custom writer is involved.
        """
        ser = self.read_file("issue60_custom_reader_endblock.ser")
        pobj = javaobj.loads(ser)
        self.assertIsNone(pobj.superItems)
        self.assertIsNone(pobj.items)
        self.assertEqual(pobj.name, "test")
        self.assertEqual(pobj.port, 443)


# ------------------------------------------------------------------------------
# JavaObjectMarshaller branch tests (built directly in Python: no Java
# fixture needed, since the marshaller only serializes existing beans).
# ------------------------------------------------------------------------------


class TestMarshallerBranches(unittest.TestCase):
    """Direct unit tests for javaobj.v1.marshaller branch coverage."""

    @staticmethod
    def _make_class(name, flags, fields_names=(), fields_types=(), superclass=None):
        cls = javaobj.beans.JavaClass()
        cls.name = name
        cls.serialVersionUID = 0
        cls.flags = flags
        cls.fields_names = list(fields_names)
        cls.fields_types = list(fields_types)
        cls.superclass = superclass
        return cls

    def test_add_transformer_dump(self):
        class UpperCaseTransformer(object):
            def transform(self, obj):
                return obj

        m = javaobj.JavaObjectMarshaller()
        m.add_transformer(UpperCaseTransformer())
        self.assertEqual(len(m.object_transformers), 1)

        cls = self._make_class("Foo", int(ClassDescFlags.SC_SERIALIZABLE))
        obj = javaobj.beans.JavaObject()
        obj.classdesc = cls
        data = javaobj.dumps(obj, UpperCaseTransformer())
        self.assertTrue(data.startswith(b"\xac\xed\x00\x05"))

    def test_load_with_transformer(self):
        class NoopTransformer(javaobj.DefaultObjectTransformer):
            pass

        jobj = self.read_file_class_helper("testBoolean.ser")
        pobj = javaobj.loads(jobj, NoopTransformer())
        self.assertEqual(pobj, chr(0))

    @staticmethod
    def read_file_class_helper(filename):
        for subfolder in ("java", ""):
            found_file = os.path.join(os.path.dirname(__file__), subfolder, filename)
            if os.path.exists(found_file):
                with open(found_file, "rb") as filep:
                    return filep.read()
        raise IOError("File not found: {0}".format(filename))

    def test_write_none(self):
        self.assertEqual(javaobj.dumps(None), b"\xac\xed\x00\x05\x70")

    def test_write_unsupported_type(self):
        with self.assertRaises(RuntimeError):
            javaobj.dumps(12345)

    def test_write_byte_array(self):
        cls = self._make_class("[B", int(ClassDescFlags.SC_SERIALIZABLE))
        arr = javaobj.beans.JavaByteArray(b"ABC", classdesc=cls)
        data = javaobj.dumps(arr)
        self.assertTrue(data.startswith(b"\xac\xed\x00\x05"))

    def test_write_enum(self):
        cls = self._make_class(
            "MyEnum",
            int(ClassDescFlags.SC_SERIALIZABLE) | int(ClassDescFlags.SC_ENUM),
        )
        enum_obj = javaobj.beans.JavaEnum(constant=javaobj.beans.JavaString("RED"))
        enum_obj.classdesc = cls
        data = javaobj.dumps(enum_obj)
        self.assertTrue(data.startswith(b"\xac\xed\x00\x05"))

    def test_writestring_reference_reuse(self):
        m = javaobj.JavaObjectMarshaller()
        m.object_stream = BytesIO()
        m.references = []
        m._writeString(javaobj.beans.JavaString("hi"))
        m._writeString(javaobj.beans.JavaString("hi"))
        self.assertEqual(len(m.references), 1)

    def test_write_blockdata_large(self):
        m = javaobj.JavaObjectMarshaller()
        m.object_stream = BytesIO()
        m.write_blockdata("x" * 300)
        data = m.object_stream.getvalue()
        # Slice (not index) so this works the same on Python 2 (str) and
        # Python 3 (bytes): indexing a str/bytes differs across versions.
        self.assertEqual(data[0:1], struct.pack(">B", int(TerminalCode.TC_BLOCKDATALONG)))

    def test_write_object_attribute_error(self):
        cls = self._make_class(
            "Foo",
            int(ClassDescFlags.SC_SERIALIZABLE),
            fields_names=["missing"],
            fields_types=[javaobj.beans.JavaString("I")],
        )
        obj = javaobj.beans.JavaObject()
        obj.classdesc = cls
        with self.assertRaises(AttributeError):
            javaobj.dumps(obj)

    def test_write_object_annotations(self):
        cls = self._make_class(
            "Foo",
            int(ClassDescFlags.SC_SERIALIZABLE) | int(ClassDescFlags.SC_WRITE_METHOD),
        )
        obj = javaobj.beans.JavaObject()
        obj.classdesc = cls
        obj.annotations = [None, javaobj.beans.JavaString("hi")]
        data = javaobj.dumps(obj)
        self.assertTrue(data.startswith(b"\xac\xed\x00\x05"))

    def test_write_array_nested(self):
        cls_inner = self._make_class("[B", int(ClassDescFlags.SC_SERIALIZABLE))
        inner_arr = javaobj.beans.JavaByteArray(b"AB", classdesc=cls_inner)

        cls_outer = self._make_class("[[B", int(ClassDescFlags.SC_SERIALIZABLE))
        outer_arr = javaobj.beans.JavaArray(classdesc=cls_outer)
        outer_arr.append(inner_arr)

        data = javaobj.dumps(outer_arr)
        self.assertTrue(data.startswith(b"\xac\xed\x00\x05"))

    def test_write_value_primitive_types(self):
        m = javaobj.JavaObjectMarshaller()
        m.object_stream = BytesIO()
        m._write_value(TypeCode.TYPE_SHORT, 5)
        m._write_value(TypeCode.TYPE_LONG, 123456789012)
        m._write_value(TypeCode.TYPE_FLOAT, 1.5)
        m._write_value(TypeCode.TYPE_DOUBLE, 2.5)
        self.assertEqual(len(m.object_stream.getvalue()), 2 + 8 + 4 + 8)

    def test_write_value_class_field(self):
        m = javaobj.JavaObjectMarshaller()
        m.object_stream = BytesIO()
        m.references = []
        cls = self._make_class("java.lang.Object", int(ClassDescFlags.SC_SERIALIZABLE))
        m._write_value(TypeCode.TYPE_OBJECT, cls)
        self.assertTrue(m.object_stream.getvalue())

    def test_write_value_string_field(self):
        m = javaobj.JavaObjectMarshaller()
        m.object_stream = BytesIO()
        m.references = []
        m._write_value(TypeCode.TYPE_OBJECT, "plain string")
        self.assertTrue(m.object_stream.getvalue())

    def test_write_value_unknown_object_typecode(self):
        m = javaobj.JavaObjectMarshaller()
        m.object_stream = BytesIO()
        m.references = []
        with self.assertRaises(RuntimeError):
            m._write_value(TypeCode.TYPE_OBJECT, 12345)

    def test_write_value_unknown_typecode(self):
        m = javaobj.JavaObjectMarshaller()
        m.object_stream = BytesIO()
        with self.assertRaises(RuntimeError):
            m._write_value(999, 1)

    def test_convert_type_to_char_variants(self):
        m = javaobj.JavaObjectMarshaller()
        self.assertEqual(m._convert_type_to_char(TypeCode.TYPE_BYTE), TypeCode.TYPE_BYTE.value)
        self.assertEqual(m._convert_type_to_char(66), 66)
        with self.assertRaises(RuntimeError):
            m._convert_type_to_char(["A"])


# ------------------------------------------------------------------------------
# JavaObjectUnmarshaller branch tests (hand-crafted byte streams)
# ------------------------------------------------------------------------------


class TestUnmarshallerBranches(unittest.TestCase):
    """Direct unit tests for javaobj.v1.unmarshaller branch coverage."""

    def test_none_stream(self):
        with self.assertRaises(IOError):
            javaobj.JavaObjectUnmarshaller(None)

    def test_bad_header(self):
        with self.assertRaises(IOError):
            javaobj.loads(b"\x00\x00\x00\x05")

    def test_unknown_opcode(self):
        # Also exercises readObject()'s except-branch and _oops_dump_state().
        with self.assertRaises(RuntimeError):
            javaobj.loads(STREAM_MAGIC + b"\x00")

    def test_truncated_stream(self):
        with self.assertRaises(RuntimeError):
            javaobj.loads(STREAM_MAGIC)

    def test_unexpected_opcode_in_expect(self):
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + _tc(TerminalCode.TC_STRING)
        with self.assertRaises(IOError):
            javaobj.loads(data)

    def test_invalid_field_typecode(self):
        cd = _classdesc_bytes(
            "Foo",
            int(ClassDescFlags.SC_SERIALIZABLE),
            field_bytes=struct.pack(">B", 0xFF) + _utf("x"),
            nb_fields=1,
        )
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + cd
        with self.assertRaises(RuntimeError):
            javaobj.loads(data)

    def test_class_annotation_not_implemented(self):
        cd = _classdesc_bytes(
            "Foo",
            int(ClassDescFlags.SC_SERIALIZABLE),
            class_annotation=_tc(TerminalCode.TC_NULL),
        )
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + cd
        with self.assertRaises(NotImplementedError):
            javaobj.loads(data)

    def test_external_contents_not_implemented(self):
        cd = _classdesc_bytes("Foo", int(ClassDescFlags.SC_EXTERNALIZABLE))
        data = STREAM_MAGIC + _tc(TerminalCode.TC_OBJECT) + cd
        with self.assertRaises(NotImplementedError):
            javaobj.loads(data)

    def test_array_field_type_assertion(self):
        field = struct.pack(">B", ord("[")) + _utf("arr")
        field += _tc(TerminalCode.TC_REFERENCE) + struct.pack(">L", int(StreamConstants.BASE_REFERENCE_IDX))
        cd = _classdesc_bytes(
            "Foo",
            int(ClassDescFlags.SC_SERIALIZABLE),
            field_bytes=field,
            nb_fields=1,
        )
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + cd
        with self.assertRaises(AssertionError):
            javaobj.loads(data)

    def test_longstring(self):
        data = STREAM_MAGIC + _tc(TerminalCode.TC_LONGSTRING) + struct.pack(">Q", 5) + b"hello"
        result = javaobj.loads(data)
        self.assertEqual(result, "hello")

    def test_blockdata_long(self):
        data = STREAM_MAGIC + _tc(TerminalCode.TC_BLOCKDATALONG) + struct.pack(">I", 5) + b"hello"
        result = javaobj.loads(data)
        self.assertEqual(result, "hello")

    @unittest.skipIf(numpy is None, "numpy is not installed")
    def test_numpy_array(self):
        for subfolder in ("java", ""):
            found_file = os.path.join(os.path.dirname(__file__), subfolder, "objArrays.ser")
            if os.path.exists(found_file):
                break
        else:
            self.skipTest("objArrays.ser not found")

        with open(found_file, "rb") as fd:
            pobj = javaobj.load(fd, use_numpy_arrays=True)
        arr = pobj.integerArr
        self.assertIsInstance(arr, numpy.ndarray)

    def test_read_value_direct(self):
        data = (
            STREAM_MAGIC
            + struct.pack(">b", -5)
            + struct.pack(">h", 300)
            + struct.pack(">q", 123456789012)
            + struct.pack(">d", 3.14)
        )
        um = javaobj.JavaObjectUnmarshaller(BytesIO(data))
        self.assertEqual(um._read_value(TypeCode.TYPE_BYTE, 0), -5)
        self.assertEqual(um._read_value(TypeCode.TYPE_SHORT, 0), 300)
        self.assertEqual(um._read_value(TypeCode.TYPE_LONG, 0), 123456789012)
        self.assertAlmostEqual(um._read_value(TypeCode.TYPE_DOUBLE, 0), 3.14)

        # White-box: raw-int and raw-bytes typecode forms (never produced
        # by the parser itself, but accepted by the method's signature).
        um2 = javaobj.JavaObjectUnmarshaller(BytesIO(STREAM_MAGIC + struct.pack(">i", 42)))
        self.assertEqual(um2._read_value(int(TypeCode.TYPE_INTEGER), 0), 42)

        um3 = javaobj.JavaObjectUnmarshaller(BytesIO(STREAM_MAGIC + struct.pack(">i", 43)))
        self.assertEqual(um3._read_value(b"I", 0), 43)


# ------------------------------------------------------------------------------
# Direct bean unit tests (dunder methods rarely hit by fixture round-trips)
# ------------------------------------------------------------------------------


class TestBeansDirect(unittest.TestCase):
    """Direct unit tests for javaobj.v1.beans."""

    def test_java_object_hash(self):
        obj = javaobj.beans.JavaObject()
        self.assertEqual(hash(obj), id(obj))

    def test_java_object_eq(self):
        cls = javaobj.beans.JavaClass()
        cls.name = "Foo"
        cls.fields_names = []

        a = javaobj.beans.JavaObject()
        a.classdesc = cls
        b = javaobj.beans.JavaObject()
        b.classdesc = cls
        self.assertEqual(a, b)
        self.assertNotEqual(a, "not a java object")

    def test_java_object_eq_field_mismatch(self):
        cls = javaobj.beans.JavaClass()
        cls.name = "Foo"
        cls.fields_names = ["x"]

        a = javaobj.beans.JavaObject()
        a.classdesc = cls
        a.x = 1
        b = javaobj.beans.JavaObject()
        b.classdesc = cls
        b.x = 2
        self.assertNotEqual(a, b)

    def test_java_array_hash(self):
        arr = javaobj.beans.JavaArray()
        self.assertIsInstance(hash(arr), int)

    def test_java_byte_array_str_and_getitem(self):
        arr = javaobj.beans.JavaByteArray(b"ABC")
        self.assertEqual(str(arr), "JavaByteArray({0})".format((65, 66, 67)))
        self.assertEqual(arr[0], 65)
        self.assertEqual(list(arr), [65, 66, 67])
        self.assertEqual(len(arr), 3)


# ------------------------------------------------------------------------------
# Direct transformer unit tests (white-box: no real serialized stream needed)
# ------------------------------------------------------------------------------


class TestTransformersDirect(unittest.TestCase):
    """Direct unit tests for javaobj.v1.transformers branch coverage."""

    def _make_time(self):
        return javaobj.transformers.DefaultObjectTransformer.JavaTime(None)

    def test_java_time_unhandled_type(self):
        jt = self._make_time()
        jt.annotations = [chr(99)]
        jt.__extra_loading__(None)  # logs an error, does not raise

    def test_java_time_local_time_branches(self):
        jt = self._make_time()
        jt.do_local_time(None, struct.pack(">b", -5))
        self.assertEqual(jt.hour, 4)  # ~(-5) == 4

        jt = self._make_time()
        jt.do_local_time(None, struct.pack(">bb", 5, -3))
        self.assertEqual(jt.minute, 2)  # ~(-3) == 2

        jt = self._make_time()
        jt.do_local_time(None, struct.pack(">bbb", 5, 3, -2))
        self.assertEqual(jt.second, 1)  # ~(-2) == 1

        jt = self._make_time()
        jt.do_local_time(None, struct.pack(">bbbi", 5, 3, 2, 12345))
        self.assertEqual(jt.nano, 12345)

    def test_java_time_zone_offset_large(self):
        jt = self._make_time()
        jt.do_zone_offset(None, struct.pack(">bi", 127, 999999))
        self.assertEqual(jt.offset, 999999)

    def test_java_time_year_month_day(self):
        jt = self._make_time()
        jt.do_year(None, struct.pack(">i", 2026))
        self.assertEqual(jt.year, 2026)

        jt = self._make_time()
        jt.do_year_month(None, struct.pack(">ib", 2026, 8))
        self.assertEqual((jt.year, jt.month), (2026, 8))

        jt = self._make_time()
        jt.do_month_day(None, struct.pack(">bb", 8, 12))
        self.assertEqual((jt.month, jt.day), (8, 12))

    def test_java_time_period(self):
        jt = self._make_time()
        jt.do_period(None, struct.pack(">iii", 1, 2, 3))
        self.assertEqual((jt.year, jt.month, jt.day), (1, 2, 3))

    def test_java_time_offset_time(self):
        """An offset time is a local time followed by a zone offset."""
        jt = self._make_time()
        jt.do_offset_time(
            None, struct.pack(">bbbi", 5, 3, 2, 12345) + struct.pack(">b", 4)
        )
        self.assertEqual((jt.hour, jt.minute, jt.second), (5, 3, 2))
        self.assertEqual(jt.nano, 12345)
        self.assertEqual(jt.offset, 4 * 900)

    def test_java_time_offset_date_time(self):
        """An offset date time is a local date time and a zone offset."""
        jt = self._make_time()
        jt.do_offset_date_time(
            None,
            struct.pack(">ibb", 2026, 8, 12)
            + struct.pack(">bbbi", 5, 3, 2, 12345)
            + struct.pack(">b", 4),
        )
        self.assertEqual((jt.year, jt.month, jt.day), (2026, 8, 12))
        self.assertEqual((jt.hour, jt.minute, jt.second), (5, 3, 2))
        self.assertEqual(jt.offset, 4 * 900)

    def test_dunder_methods(self):
        transformer_cls = javaobj.transformers.DefaultObjectTransformer

        jl = transformer_cls.JavaList(None)
        self.assertIsInstance(hash(jl), int)

        jm = transformer_cls.JavaMap(None)
        self.assertIsInstance(hash(jm), int)

        js = transformer_cls.JavaSet(None)
        self.assertIsInstance(hash(js), int)

        jbool = transformer_cls.JavaBool(None)
        jbool.value = True
        self.assertTrue(bool(jbool))

        jint = transformer_cls.JavaInt(None)
        jint.value = 42
        self.assertEqual(int(jint), 42)

        jprim = transformer_cls.JavaInt(None)
        jprim.value = 1
        self.assertLess(jprim, 2)

    def test_linked_hash_map_loads_from_annotations(self):
        """
        A LinkedHashMap takes its content from the annotations of its
        HashMap parent, like a HashMap does: the first annotation is the
        block data holding the number of buckets and the size, the next
        ones are the keys and values, one after the other.
        """
        transformer_cls = javaobj.transformers.DefaultObjectTransformer
        lhm = transformer_cls.JavaLinkedHashMap(None)
        lhm.annotations = [
            struct.pack(">ii", 16, 2),
            "first",
            "1",
            "second",
            "2",
        ]
        lhm.__extra_loading__(None)
        self.assertEqual(dict(lhm), {"first": "1", "second": "2"})

    def test_linked_hash_map_empty(self):
        transformer_cls = javaobj.transformers.DefaultObjectTransformer
        lhm = transformer_cls.JavaLinkedHashMap(None)
        lhm.annotations = [struct.pack(">ii", 16, 0)]
        lhm.__extra_loading__(None)
        self.assertEqual(dict(lhm), {})


# ------------------------------------------------------------------------------


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Run tests
    unittest.main()
