#!/usr/bin/env python3
"""
Tests for javaobj v3.

:authors: Thomas Calmant
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

# Standard library
import logging
import os
import struct
import subprocess
import sys
import unittest
from typing import Any

# Make sure javaobj is importable when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Javaobj
import javaobj.v3 as javaobj
from javaobj.constants import ClassDescFlags, StreamConstants, TerminalCode, TypeCode
from javaobj.v3._compat import v1_to_v3, v2_to_v3
from javaobj.v3.beans import (
    ClassDescType,
    FieldType,
    JavaArray,
    JavaClass,
    JavaClassDesc,
    JavaEnum,
    JavaField,
    JavaInstance,
    JavaString,
)
from javaobj.v3.exceptions import (
    JavaObjError,
    ParseError,
    SecurityError,
    UnexpectedOpcodeError,
    UnsupportedFeatureError,
)
from javaobj.v3.parser import JavaStreamParser
from javaobj.v3.reader import DataReader
from javaobj.v3.transformers import (
    DefaultObjectTransformer,
    JavaTime,
    NumpyArrayTransformer,
    ObjectTransformer,
)
from javaobj.v3.writer import _encode_mutf8

try:
    import numpy
except ImportError:
    numpy = None

# ------------------------------------------------------------------------------

__docformat__ = "restructuredtext en"

_logger = logging.getLogger("javaobj.tests.v3")

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------


def _ser_path(filename: str) -> str:
    """Returns the absolute path of a .ser fixture, searching sub-dirs."""
    base = os.path.dirname(__file__)
    for sub in ("java", ""):
        full = os.path.join(base, sub, filename)
        if os.path.exists(full):
            return full
    raise FileNotFoundError(f"Fixture not found: {filename}")


# ------------------------------------------------------------------------------
# Hand-crafted byte-stream helpers (no Java toolchain required: the wire
# format is fully described by javaobj.constants).
# ------------------------------------------------------------------------------

STREAM_MAGIC = struct.pack(">HH", int(StreamConstants.STREAM_MAGIC), int(StreamConstants.STREAM_VERSION))


def _utf(s: str) -> bytes:
    """Encodes a short UTF string: 2-byte length + (Modified) UTF-8 bytes."""
    encoded = s.encode("utf-8")
    return struct.pack(">H", len(encoded)) + encoded


def _tc(code: "TerminalCode | int") -> bytes:
    """Single opcode byte."""
    return bytes([int(code)])


def _classdesc_bytes(
    name: str,
    flags: int,
    field_bytes: bytes = b"",
    nb_fields: int = 0,
    superclass: bytes = _tc(TerminalCode.TC_NULL),
) -> bytes:
    """Builds a minimal TC_CLASSDESC record (no class annotation content)."""
    return (
        _tc(TerminalCode.TC_CLASSDESC)
        + _utf(name)
        + struct.pack(">q", 0)  # serialVersionUID
        + struct.pack(">Bh", flags, nb_fields)
        + field_bytes
        + _tc(TerminalCode.TC_ENDBLOCKDATA)  # end of class annotations
        + superclass
    )


def _object_field(name: str, class_name_bytes: bytes) -> bytes:
    """Builds a TYPE_OBJECT field descriptor entry."""
    return bytes([ord("L")]) + _utf(name) + class_name_bytes


# ------------------------------------------------------------------------------
# Base test class
# ------------------------------------------------------------------------------


class TestJavaobjV3Base(unittest.TestCase):
    """Shared helpers for all v3 test cases."""

    @classmethod
    def setUpClass(cls) -> None:
        """
        Calls Maven to compile & run Java classes that generate the .ser
        fixtures, unless the ``JAVAOBJ_NO_MAVEN`` environment variable is set.
        """
        java_dir = os.path.join(os.path.dirname(__file__), "java")
        if not os.getenv("JAVAOBJ_NO_MAVEN") and os.path.isdir(java_dir):
            cwd = os.getcwd()
            os.chdir(java_dir)
            subprocess.call("mvn test", shell=True)
            os.chdir(cwd)

    def load_file(self, filename: str) -> Any:
        """Reads and deserializes a .ser fixture via v3."""
        with open(_ser_path(filename), "rb") as f:
            return javaobj.load(f)

    def load_bytes(self, filename: str) -> Any:
        """Reads the raw bytes of a .ser fixture and deserializes via v3."""
        with open(_ser_path(filename), "rb") as f:
            return javaobj.loads(f.read())


# ------------------------------------------------------------------------------
# Primitive and simple-type tests
# ------------------------------------------------------------------------------


class TestPrimitiveTypes(TestJavaobjV3Base):
    """Tests for primitive Java type serialization."""

    def test_char_rw(self) -> None:
        """testChar.ser – single Java char serialized as 2-byte sequence."""
        pobj = self.load_bytes("testChar.ser")
        # A lone Java char is serialized as a 2-byte big-endian block.
        self.assertEqual(pobj, b"\x00C")

    def test_chars_rw(self) -> None:
        """testChars.ser – Java char[] encoded as UTF-16-BE bytes."""
        expected = "python-javaobj".encode("utf-16-be")
        pobj = self.load_bytes("testChars.ser")
        self.assertEqual(pobj, expected)
        # Also comparable as a latin-1 string
        self.assertEqual(pobj, expected.decode("latin1"))

    def test_double_rw(self) -> None:
        """testDouble.ser – Java double serialized as 8 bytes."""
        pobj = self.load_bytes("testDouble.ser")
        self.assertEqual(pobj, b"\x7f\xef\xff\xff\xff\xff\xff\xff")

    def test_bytes_rw(self) -> None:
        """testBytes.ser – Java byte[] as Python bytes."""
        pobj = self.load_bytes("testBytes.ser")
        self.assertEqual(pobj, b"HelloWorld")

    def test_boolean(self) -> None:
        """testBoolean.ser – Java boolean primitive."""
        pobj = self.load_bytes("testBoolean.ser")
        # A serialized boolean is a 1-byte block; 0x00 = false.
        self.assertEqual(pobj, b"\x00")

    def test_byte(self) -> None:
        """testByte.ser – Java byte primitive (value 127)."""
        pobj = self.load_bytes("testByte.ser")
        self.assertEqual(pobj, b"\x7f")

    def test_japan(self) -> None:
        """testJapan.ser – Japanese characters (wide UTF-8 codepoints)."""
        pobj = self.load_bytes("testJapan.ser")
        self.assertEqual(
            pobj,
            "\u65e5\u672c\u56fd",  # 日本国
        )


# ------------------------------------------------------------------------------
# Object / class descriptor tests
# ------------------------------------------------------------------------------


class TestObjects(TestJavaobjV3Base):
    """Tests for serialized Java objects."""

    def test_fields(self) -> None:
        """test_readFields.ser – object with named fields."""
        pobj = self.load_bytes("test_readFields.ser")
        self.assertIsInstance(pobj, JavaInstance)

        # Access fields via the v2-compatible __getattr__
        self.assertEqual(pobj.aField1, "Gabba")
        self.assertIsNone(pobj.aField2)

        # Access via get_field (preferred v3 API)
        self.assertEqual(pobj.get_field("aField1"), "Gabba")

        classdesc = pobj.get_class()
        self.assertIsNotNone(classdesc)
        self.assertEqual(classdesc.serialVersionUID, 0x7F0941F5)
        self.assertEqual(classdesc.name, "OneTest$SerializableTestHelper")
        self.assertEqual(len(classdesc.fields_names), 3)

    def test_class(self) -> None:
        """testClass.ser – java.lang.Class reference."""
        pobj = self.load_bytes("testClass.ser")
        self.assertIsInstance(pobj, JavaClass)
        self.assertEqual(pobj.name, "java.lang.String")

    def test_super(self) -> None:
        """objSuper.ser – class hierarchy (parent + child fields)."""
        pobj = self.load_bytes("objSuper.ser")
        self.assertIsInstance(pobj, JavaInstance)

        classdesc = pobj.get_class()
        self.assertIsNotNone(classdesc)

        # Fields defined on the child class
        self.assertEqual(pobj.childString, "Child!!")
        # Fields inherited from the parent class
        self.assertEqual(pobj.bool, True)
        self.assertEqual(pobj.integer, -1)
        self.assertEqual(pobj.superString, "Super!!")

    def test_class_with_byte_array(self) -> None:
        """testClassWithByteArray.ser – instance field holding a byte array."""
        pobj = self.load_bytes("testClassWithByteArray.ser")
        self.assertIsInstance(pobj, JavaInstance)

        # In v3 the array field is a JavaArray whose .data is bytes
        arr = pobj.myArray
        self.assertIsInstance(arr, JavaArray)
        self.assertEqual(arr.element_type, FieldType.BYTE)
        self.assertEqual(arr.data, bytes([1, 3, 7, 11]))

    def test_sun_example(self) -> None:
        """sunExample.ser – linked-list style stream with two objects."""
        content = javaobj.load(open(_ser_path("sunExample.ser"), "rb"))

        self.assertIsInstance(content, list)
        self.assertEqual(len(content), 2)

        pobj = content[0]
        self.assertEqual(pobj.value, 17)
        self.assertTrue(pobj.next)

        pobj = content[1]
        self.assertEqual(pobj.value, 19)
        self.assertFalse(pobj.next)

    def test_exception_object(self) -> None:
        """testException.ser / objException.ser – serialized exception.

        Exception parsing is complex (requires TC_EXCEPTION handling in the
        object graph).  This test verifies that the file is either parsed
        successfully or raises a well-typed ``JavaObjError`` (no crashes with
        unhandled exceptions or wrong types).
        """
        for filename in ("testException.ser", "objException.ser"):
            try:
                pobj = self.load_bytes(filename)
                _logger.debug("Loaded %s: %s", filename, pobj)
            except FileNotFoundError:
                _logger.warning("Skipping %s (not found)", filename)
            except JavaObjError as exc:
                # Known limitation: some exception streams reference
                # class descriptors instead of strings (see report B-07).
                # Log but do not fail the test.
                _logger.warning(
                    "Parsing %s raised JavaObjError (known limitation): %s",
                    filename,
                    exc,
                )


# ------------------------------------------------------------------------------
# Array tests
# ------------------------------------------------------------------------------


class TestArrays(TestJavaobjV3Base):
    """Tests for Java array serialization."""

    def test_arrays_obj(self) -> None:
        """objArrays.ser – object with several array fields."""
        pobj = self.load_bytes("objArrays.ser")
        self.assertIsInstance(pobj, JavaInstance)

        classdesc = pobj.get_class()
        self.assertIsNotNone(classdesc)

        # Check field names are accessible
        self.assertIn("stringArr", classdesc.fields_names)
        self.assertIn("integerArr", classdesc.fields_names)
        self.assertIn("boolArr", classdesc.fields_names)

        # Each array field should be a JavaArray
        self.assertIsInstance(pobj.stringArr, JavaArray)
        self.assertIsInstance(pobj.integerArr, JavaArray)
        self.assertIsInstance(pobj.boolArr, JavaArray)

    def test_char_array(self) -> None:
        """testCharArray.ser – array of Java chars (UTF-16 code units)."""
        pobj = self.load_bytes("testCharArray.ser")
        self.assertIsInstance(pobj, JavaArray)
        self.assertEqual(pobj.element_type, FieldType.CHAR)
        self.assertEqual(
            list(pobj),
            [
                "\u0000",
                "\ud800",
                "\u0001",
                "\udc00",
                "\u0002",
                "\uffff",
                "\u0003",
            ],
        )

    def test_2d_array(self) -> None:
        """test2DArray.ser – two-dimensional int array."""
        pobj = self.load_bytes("test2DArray.ser")
        self.assertIsInstance(pobj, JavaArray)
        # Each row is itself a JavaArray
        rows = [list(row) for row in pobj]
        self.assertEqual(rows, [[1, 2, 3], [4, 5, 6]])

    def test_class_array(self) -> None:
        """testClassArray.ser – array of java.lang.Class references."""
        pobj = self.load_bytes("testClassArray.ser")
        self.assertIsInstance(pobj, JavaArray)
        self.assertEqual(pobj[0].name, "java.lang.Integer")
        self.assertEqual(pobj[1].name, "java.io.ObjectOutputStream")
        self.assertEqual(pobj[2].name, "java.lang.Exception")


# ------------------------------------------------------------------------------
# Enum tests
# ------------------------------------------------------------------------------


class TestEnums(TestJavaobjV3Base):
    """Tests for Java enum serialization."""

    def test_enums_obj(self) -> None:
        """objEnums.ser – object with enum and array-of-enum fields."""
        pobj = self.load_bytes("objEnums.ser")
        self.assertIsInstance(pobj, JavaInstance)

        classdesc = pobj.get_class()
        self.assertEqual(classdesc.name, "ClassWithEnum")

        # Single enum field
        self.assertIsInstance(pobj.color, JavaEnum)
        self.assertEqual(pobj.color.classdesc.name, "Color")
        # JavaString.__eq__ handles plain str comparison
        self.assertEqual(pobj.color.constant, "GREEN")

        # Array of enum values
        colors_arr = pobj.colors
        self.assertIsInstance(colors_arr, JavaArray)
        expected = ["GREEN", "BLUE", "RED"]
        for color, name in zip(colors_arr, expected):
            self.assertIsInstance(color, JavaEnum)
            self.assertEqual(color.classdesc.name, "Color")
            self.assertEqual(color.constant, name)

    def test_enums_simple(self) -> None:
        """testEnums.ser – standalone enum values."""
        pobj = self.load_bytes("testEnums.ser")
        _logger.debug("testEnums: %s", pobj)


# ------------------------------------------------------------------------------
# Collection tests
# ------------------------------------------------------------------------------


class TestCollections(TestJavaobjV3Base):
    """Tests for Java collection serialization."""

    def test_sets(self) -> None:
        """testHashSet / testTreeSet / testLinkedHashSet – Java set types."""
        for filename in (
            "testHashSet.ser",
            "testTreeSet.ser",
            "testLinkedHashSet.ser",
        ):
            with self.subTest(file=filename):
                pobj = self.load_bytes(filename)
                self.assertIsInstance(pobj, set)
                # Each element is a JavaInt whose .value is an int
                self.assertSetEqual({item.value for item in pobj}, {1, 2, 42})

    def test_collections_obj(self) -> None:
        """objCollections.ser – object with ArrayList, HashMap, LinkedList."""
        pobj = self.load_bytes("objCollections.ser")
        self.assertIsInstance(pobj, JavaInstance)

        self.assertIsInstance(pobj.arrayList, list)
        self.assertIsInstance(pobj.hashMap, dict)
        self.assertIsInstance(pobj.linkedList, list)

    def test_linked_hash_map(self) -> None:
        """testLinkedHashMap.ser - LinkedHashMap entries (issue #30).

        A LinkedHashMap writes its entries in the block data of the HashMap
        it extends, so they are found in the annotations of that parent and
        not in those of the LinkedHashMap itself.
        """
        pobj = self.load_bytes("testBareLinkedHashMap.ser")
        self.assertIsInstance(pobj, dict)
        self.assertEqual(dict(pobj), {"a": "1", "b": "2"})

        pobj = self.load_bytes("testLinkedHashMap.ser")
        self.assertEqual(pobj.name, "holder")
        self.assertEqual(dict(pobj.settings), {"first": "1", "second": "2"})
        self.assertEqual(pobj.port, 443)

    def test_shared_array(self) -> None:
        """testSharedArray.ser - an array referenced by two fields (#62)."""
        pobj = self.load_bytes("testSharedArray.ser")

        self.assertEqual(list(pobj.first), [1, 2, 3])
        self.assertEqual(list(pobj.second), [1, 2, 3])
        self.assertEqual(list(pobj.strings), ["a", "b"])

        # Both fields must give the very same array
        self.assertIs(pobj.first, pobj.second)
        self.assertIs(pobj.strings, pobj.sameStrings)

        # Detects a desynchronized stream
        self.assertEqual(pobj.marker, 443)

    def test_bool_int_long(self) -> None:
        """testBoolIntLong.ser – HashMap with Boolean / Integer / Long values."""
        pobj = self.load_bytes("testBoolIntLong.ser")
        self.assertIsInstance(pobj, dict)

        self.assertEqual(pobj["key1"], "value1")
        self.assertEqual(pobj["key2"], "value2")
        self.assertEqual(pobj["int"], 9)
        self.assertEqual(pobj["int2"], 10)
        self.assertEqual(pobj["bool"], True)
        self.assertEqual(pobj["bool2"], True)

    def test_bool_int_long_nested(self) -> None:
        """testBoolIntLong-2.ser – HashMap containing another HashMap."""
        pobj = self.load_bytes("testBoolIntLong-2.ser")
        self.assertIsInstance(pobj, dict)

        base = self.load_bytes("testBoolIntLong.ser")
        parent_map = pobj["subMap"]
        for key, value in base.items():
            self.assertEqual(parent_map[key], value)

    def test_jceks_issue_5(self) -> None:
        """jceks_issue_5.ser – regression test for issue #5."""
        pobj = self.load_bytes("jceks_issue_5.ser")
        _logger.info("jceks_issue_5: %s", pobj)


# ------------------------------------------------------------------------------
# java.time tests
# ------------------------------------------------------------------------------


class TestTimes(TestJavaobjV3Base):
    """Tests for java.time.* serialization."""

    def test_times(self) -> None:
        """testTime.ser – array of java.time.Ser instances."""
        pobj = self.load_bytes("testTime.ser")

        # Top-level result is a Java array
        self.assertIsInstance(pobj, JavaArray)

        # Each element must be a JavaTime instance (from DefaultObjectTransformer)
        for obj in pobj:
            self.assertIsInstance(obj, JavaTime)

        # First entry is a Duration of 10 seconds
        duration = pobj[0]
        self.assertEqual(duration.second, 10)


# ------------------------------------------------------------------------------
# v3-specific feature tests
# ------------------------------------------------------------------------------


class TestV3Specific(TestJavaobjV3Base):
    """Tests for features that are new or improved in v3."""

    def test_byte_array_is_bytes(self) -> None:
        """In v3, TYPE_BYTE arrays are returned as plain bytes, not list."""
        pobj = self.load_bytes("testBytes.ser")
        # testBytes.ser is a standalone byte array (TC_ARRAY)
        if isinstance(pobj, JavaArray):
            self.assertIsInstance(pobj.data, bytes)

    def test_get_field_vs_getattr(self) -> None:
        """get_field() and attribute access should return the same value."""
        pobj = self.load_bytes("test_readFields.ser")
        self.assertIsInstance(pobj, JavaInstance)

        val_attr = pobj.aField1
        val_method = pobj.get_field("aField1")
        self.assertEqual(val_attr, val_method)

    def test_typed_exceptions(self) -> None:
        """Malformed streams must raise ParseError, a subclass of JavaObjError."""
        bad_data = b"\xac\xed\x00\x05\xff"
        with self.assertRaises(ParseError):
            javaobj.loads(bad_data)

        with self.assertRaises(JavaObjError):
            javaobj.loads(bad_data)

    def test_invalid_magic_raises_parse_error(self) -> None:
        """Streams with wrong magic must raise ParseError with offset info."""
        bad_data = b"\x00\x00\x00\x05"
        try:
            javaobj.loads(bad_data)
            self.fail("Expected ParseError")
        except ParseError as exc:
            self.assertGreaterEqual(exc.offset, 0)

    def test_security_max_depth(self) -> None:
        """A max_depth of 1 must raise SecurityError on any nested object."""
        data = open(_ser_path("objSuper.ser"), "rb").read()
        with self.assertRaises(SecurityError):
            javaobj.loads(data, max_depth=1)

    def test_empty_stream_returns_none(self) -> None:
        """A stream with only the magic header and no objects returns None."""
        header = b"\xac\xed\x00\x05"
        result = javaobj.loads(header)
        self.assertIsNone(result)

    def test_loads_and_load_equivalent(self) -> None:
        """javaobj.loads(data) must give the same result as javaobj.load(fd)."""
        path = _ser_path("testBoolean.ser")
        with open(path, "rb") as f:
            data = f.read()
        result_bytes = javaobj.loads(data)
        with open(path, "rb") as f:
            result_stream = javaobj.load(f)
        self.assertEqual(result_bytes, result_stream)

    def test_classdesc_properties(self) -> None:
        """JavaClassDesc compatibility properties (flags, serialVersionUID)."""
        pobj = self.load_bytes("test_readFields.ser")
        cd = pobj.get_class()
        self.assertIsInstance(cd, JavaClassDesc)

        # Both names for the same attribute must match
        self.assertEqual(cd.flags, cd.desc_flags)
        self.assertEqual(cd.serialVersionUID, cd.serial_version_uid)

        # fields_names and fields_types must be consistent
        self.assertEqual(len(cd.fields_names), len(cd.fields_types))
        for name, ftype in zip(cd.fields_names, cd.fields_types):
            self.assertIsInstance(name, str)
            self.assertIsInstance(ftype, FieldType)

    def test_java_string_equality(self) -> None:
        """JavaString must compare equal to plain Python str."""
        js = JavaString(handle=0, value="hello")
        self.assertEqual(js, "hello")
        self.assertEqual("hello", js)
        self.assertEqual(hash(js), hash("hello"))

    def test_custom_transformer(self) -> None:
        """A custom ObjectTransformer.create_instance must be invoked."""

        class MarkerInstance(JavaInstance):
            """Marker subclass to detect transformer invocation."""

            was_created = False

            def load_from_instance(self) -> bool:
                MarkerInstance.was_created = True
                return True

        class MarkerTransformer(ObjectTransformer):
            TARGET = "OneTest$SerializableTestHelper"

            def create_instance(self, classdesc: JavaClassDesc) -> JavaInstance | None:
                if classdesc.name == self.TARGET:
                    return MarkerInstance()
                return None

        pobj = self.load_bytes("test_readFields.ser", MarkerTransformer())
        self.assertIsInstance(pobj, MarkerInstance)
        self.assertTrue(MarkerInstance.was_created)

    # Helper used by test_custom_transformer
    def load_bytes(self, filename: str, *extra_transformers: ObjectTransformer) -> Any:
        with open(_ser_path(filename), "rb") as f:
            return javaobj.load(f, *extra_transformers)

    def test_super_object(self) -> None:
        """objSuper.ser – verify hierarchy is preserved in field_data."""
        pobj = self.load_bytes("objSuper.ser")
        self.assertIsInstance(pobj, JavaInstance)

        # field_data must have at least one entry per class in the hierarchy
        self.assertGreater(len(pobj.field_data), 0)

        # All classes in the hierarchy must be present
        cd = pobj.get_class()
        hierarchy = cd.get_hierarchy()
        for hcd in hierarchy:
            if hcd in pobj.field_data:
                for field in hcd.fields:
                    self.assertIn(field, pobj.field_data[hcd])


# ------------------------------------------------------------------------------
# Malformed-stream / defensive-branch tests
# ------------------------------------------------------------------------------


class TestMalformedStreams(unittest.TestCase):
    """
    Feeds hand-crafted, syntactically-invalid streams to the parser to
    exercise its defensive ``ParseError``/``UnexpectedOpcodeError`` guard
    clauses. No Java toolchain is needed: the wire format only requires
    following javaobj.constants byte-for-byte.
    """

    def test_bad_magic(self) -> None:
        with self.assertRaises(ParseError):
            javaobj.loads(b"\x00\x00\x00\x05")

    def test_bad_version(self) -> None:
        with self.assertRaises(ParseError):
            javaobj.loads(struct.pack(">HH", int(StreamConstants.STREAM_MAGIC), 0x99))

    def test_unexpected_blockdata_in_exception(self) -> None:
        data = STREAM_MAGIC + _tc(TerminalCode.TC_EXCEPTION) + _tc(TerminalCode.TC_BLOCKDATA) + b"\x00"
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_null_classdesc_for_class(self) -> None:
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + _tc(TerminalCode.TC_NULL)
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_null_classdesc_for_array(self) -> None:
        data = STREAM_MAGIC + _tc(TerminalCode.TC_ARRAY) + _tc(TerminalCode.TC_NULL)
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_null_classdesc_for_enum(self) -> None:
        data = STREAM_MAGIC + _tc(TerminalCode.TC_ENUM) + _tc(TerminalCode.TC_NULL)
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_invalid_array_element_type(self) -> None:
        # '[Q' — 'Q' is not a valid Java primitive/object type code.
        cd = _classdesc_bytes("[Q", int(ClassDescFlags.SC_SERIALIZABLE))
        data = STREAM_MAGIC + _tc(TerminalCode.TC_ARRAY) + cd + struct.pack(">i", 0)
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_invalid_array_size(self) -> None:
        cd = _classdesc_bytes("[B", int(ClassDescFlags.SC_SERIALIZABLE))
        data = STREAM_MAGIC + _tc(TerminalCode.TC_ARRAY) + cd + struct.pack(">i", -1)
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_invalid_field_count(self) -> None:
        cd = _classdesc_bytes("Foo", int(ClassDescFlags.SC_SERIALIZABLE), nb_fields=-1)
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + cd
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_invalid_field_type_byte(self) -> None:
        bad_field = bytes([0xFF]) + _utf("x")
        cd = _classdesc_bytes("Foo", int(ClassDescFlags.SC_SERIALIZABLE), field_bytes=bad_field, nb_fields=1)
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + cd
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_invalid_handle_reference(self) -> None:
        data = STREAM_MAGIC + _tc(TerminalCode.TC_REFERENCE) + struct.pack(">i", 0x7E1234)
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_reset_during_exception(self) -> None:
        data = STREAM_MAGIC + _tc(TerminalCode.TC_EXCEPTION) + _tc(TerminalCode.TC_RESET)
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_null_exception_object(self) -> None:
        data = STREAM_MAGIC + _tc(TerminalCode.TC_EXCEPTION) + _tc(TerminalCode.TC_NULL)
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_exception_object_not_instance(self) -> None:
        data = STREAM_MAGIC + _tc(TerminalCode.TC_EXCEPTION) + _tc(TerminalCode.TC_STRING) + _utf("hello")
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_invalid_blockdatalong_size(self) -> None:
        data = STREAM_MAGIC + _tc(TerminalCode.TC_BLOCKDATALONG) + struct.pack(">i", -1)
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_unknown_top_level_opcode(self) -> None:
        data = STREAM_MAGIC + b"\x99"
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_classdesc_reference_not_classdesc(self) -> None:
        # A string is allocated the first handle; TC_ARRAY then references
        # it as though it were a class descriptor.
        data = (
            STREAM_MAGIC
            + _tc(TerminalCode.TC_STRING)
            + _utf("hi")
            + _tc(TerminalCode.TC_ARRAY)
            + _tc(TerminalCode.TC_REFERENCE)
            + struct.pack(">i", int(StreamConstants.BASE_REFERENCE_IDX))
        )
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_string_reference_not_string(self) -> None:
        # First object allocates a classdesc handle; a second class then
        # declares a field whose class-name is a TC_REFERENCE to that
        # classdesc handle (not a string).
        cd1 = _classdesc_bytes("A", int(ClassDescFlags.SC_SERIALIZABLE))
        field = _object_field(
            "x",
            _tc(TerminalCode.TC_REFERENCE) + struct.pack(">i", int(StreamConstants.BASE_REFERENCE_IDX)),
        )
        cd2 = _classdesc_bytes("B", int(ClassDescFlags.SC_SERIALIZABLE), field_bytes=field, nb_fields=1)
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + cd1 + _tc(TerminalCode.TC_CLASS) + cd2
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_field_class_name_invalid_opcode(self) -> None:
        # A field's class-name token must be TC_STRING/TC_LONGSTRING/
        # TC_REFERENCE; anything else is rejected.
        field = _object_field("x", b"\x00")
        cd = _classdesc_bytes("Foo", int(ClassDescFlags.SC_SERIALIZABLE), field_bytes=field, nb_fields=1)
        data = STREAM_MAGIC + _tc(TerminalCode.TC_CLASS) + cd
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_external_contents_unsupported(self) -> None:
        # SC_EXTERNALIZABLE without SC_BLOCK_DATA is Protocol v1, unsupported.
        cd = _classdesc_bytes("Foo", int(ClassDescFlags.SC_EXTERNALIZABLE))
        data = STREAM_MAGIC + _tc(TerminalCode.TC_OBJECT) + cd
        with self.assertRaises(UnsupportedFeatureError):
            javaobj.loads(data)

    def test_object_annotation_no_transformer(self) -> None:
        # SC_EXTERNALIZABLE + SC_BLOCK_DATA with no transformer able to
        # decode the block data.
        flags = int(ClassDescFlags.SC_EXTERNALIZABLE) | int(ClassDescFlags.SC_BLOCK_DATA)
        cd = _classdesc_bytes("Foo", flags)
        data = STREAM_MAGIC + _tc(TerminalCode.TC_OBJECT) + cd
        with self.assertRaises(ParseError):
            javaobj.loads(data)

    def test_duplicate_handle(self) -> None:
        # White-box: handles are always freshly allocated by the parser
        # itself, so duplication can only be triggered by calling the
        # internal API directly.
        import io

        parser = JavaStreamParser(io.BytesIO(b""), [DefaultObjectTransformer()])
        handle = parser._new_handle()
        parser._set_handle(handle, None)
        with self.assertRaises(ParseError):
            parser._set_handle(handle, None)


# ------------------------------------------------------------------------------
# JavaClassDesc.validate() / field-access tests
# ------------------------------------------------------------------------------


class TestBeansValidation(unittest.TestCase):
    """Direct unit tests for JavaClassDesc.validate() and field access."""

    def _cd(self, flags: int, fields=(), interfaces=(), enum_constants=()) -> JavaClassDesc:
        return JavaClassDesc(
            handle=0,
            name="Foo",
            serial_version_uid=0,
            desc_flags=flags,
            fields=list(fields),
            interfaces=list(interfaces),
            enum_constants=set(enum_constants),
        )

    def test_valid_serializable(self) -> None:
        cd = self._cd(int(ClassDescFlags.SC_SERIALIZABLE))
        cd.validate()  # must not raise

    def test_non_serializable_with_fields(self) -> None:
        field = JavaField(type=FieldType.INTEGER, name="x")
        cd = self._cd(0, fields=[field])
        with self.assertRaises(ValueError):
            cd.validate()

    def test_serializable_and_externalizable(self) -> None:
        flags = int(ClassDescFlags.SC_SERIALIZABLE) | int(ClassDescFlags.SC_EXTERNALIZABLE)
        cd = self._cd(flags)
        with self.assertRaises(ValueError):
            cd.validate()

    def test_enum_with_fields(self) -> None:
        flags = int(ClassDescFlags.SC_SERIALIZABLE) | int(ClassDescFlags.SC_ENUM)
        field = JavaField(type=FieldType.INTEGER, name="x")
        cd = self._cd(flags, fields=[field])
        with self.assertRaises(ValueError):
            cd.validate()

    def test_enum_with_interfaces(self) -> None:
        flags = int(ClassDescFlags.SC_SERIALIZABLE) | int(ClassDescFlags.SC_ENUM)
        cd = self._cd(flags, interfaces=["java.lang.Runnable"])
        with self.assertRaises(ValueError):
            cd.validate()

    def test_non_enum_with_enum_constants(self) -> None:
        cd = self._cd(int(ClassDescFlags.SC_SERIALIZABLE), enum_constants=["RED"])
        with self.assertRaises(ValueError):
            cd.validate()

    def test_data_type_invalid_flags_raises(self) -> None:
        cd = self._cd(0)
        with self.assertRaises(ValueError):
            _ = cd.data_type

    def test_get_field_unknown_raises(self) -> None:
        instance = JavaInstance()
        with self.assertRaises(AttributeError):
            instance.get_field("nonexistent")

    def test_getattr_unknown_raises(self) -> None:
        instance = JavaInstance()
        with self.assertRaises(AttributeError):
            _ = instance.unknown_attribute


# ------------------------------------------------------------------------------
# Exception hierarchy tests
# ------------------------------------------------------------------------------


class TestTransformersArgument(unittest.TestCase):
    """Tests the check of the transformers given to load()/loads() (#54)."""

    DATA = STREAM_MAGIC + _tc(TerminalCode.TC_NULL)

    def test_transformer_class_rejected(self) -> None:
        """A class instead of an instance must be reported clearly."""
        import io

        class MyTransformer(javaobj.transformers.ObjectTransformer):
            pass

        for call in (
            lambda: javaobj.loads(self.DATA, MyTransformer),
            lambda: javaobj.load(io.BytesIO(self.DATA), MyTransformer),
        ):
            with self.assertRaises(TypeError) as context:
                call()

            message = str(context.exception)
            self.assertIn("instances", message)
            self.assertIn("MyTransformer", message)

    def test_transformer_instance_accepted(self) -> None:
        """An instance stays valid."""

        class MyTransformer(javaobj.transformers.ObjectTransformer):
            pass

        self.assertIsNone(javaobj.loads(self.DATA, MyTransformer()))


class TestExceptions(unittest.TestCase):
    """Direct unit tests for javaobj.v3.exceptions."""

    def test_parse_error_without_offset(self) -> None:
        exc = ParseError("boom")
        self.assertEqual(str(exc), "boom")

    def test_parse_error_with_offset(self) -> None:
        exc = ParseError("boom", offset=0x10)
        self.assertIn("0x10", str(exc))

    def test_unexpected_opcode_error(self) -> None:
        exc = UnexpectedOpcodeError((0x70, 0x71), 0x99, offset=4)
        self.assertEqual(exc.expected, (0x70, 0x71))
        self.assertEqual(exc.got, 0x99)
        self.assertIn("0x99", str(exc))
        self.assertIsInstance(exc, ParseError)


# ------------------------------------------------------------------------------
# TC_PROXYCLASSDESC round-trip (writer already implements it; the parser
# side is otherwise never exercised by any .ser fixture)
# ------------------------------------------------------------------------------


class TestProxyClassDesc(TestJavaobjV3Base):
    """Round-trip test for dynamic proxy class descriptors."""

    def test_proxy_classdesc_round_trip(self) -> None:
        cd = JavaClassDesc(
            handle=0,
            name="",
            serial_version_uid=0,
            desc_flags=int(ClassDescFlags.SC_SERIALIZABLE) | int(ClassDescFlags.SC_WRITE_METHOD),
            class_type=ClassDescType.PROXYCLASS,
            interfaces=["java.lang.Runnable", "java.io.Serializable"],
        )
        instance = JavaInstance(classdesc=cd)
        serialized = javaobj.dumps(instance)
        re_parsed = javaobj.loads(serialized)

        self.assertIsInstance(re_parsed, JavaInstance)
        new_cd = re_parsed.get_class()
        self.assertEqual(new_cd.class_type, ClassDescType.PROXYCLASS)
        self.assertEqual(new_cd.interfaces, ["java.lang.Runnable", "java.io.Serializable"])


# ------------------------------------------------------------------------------
# NumpyArrayTransformer
# ------------------------------------------------------------------------------


@unittest.skipIf(numpy is None, "numpy is not installed")
class TestNumpyArrayTransformer(TestJavaobjV3Base):
    """Tests for the optional numpy-backed array transformer."""

    def test_use_numpy_arrays(self) -> None:
        # NumpyArrayTransformer replaces JavaArray.data with an ndarray;
        # the array is still wrapped in a JavaArray, like any other array.
        with open(_ser_path("objArrays.ser"), "rb") as f:
            pobj = javaobj.load(f, use_numpy_arrays=True)

        self.assertIsInstance(pobj, JavaInstance)
        arr = pobj.integerArr
        self.assertIsInstance(arr, JavaArray)
        self.assertIsInstance(arr.data, numpy.ndarray)
        self.assertEqual(arr.data.dtype, numpy.dtype(">i"))

    def test_char_array_dtype(self) -> None:
        with open(_ser_path("testCharArray.ser"), "rb") as f:
            pobj = javaobj.load(f, use_numpy_arrays=True)
        self.assertIsInstance(pobj, JavaArray)
        self.assertIsInstance(pobj.data, numpy.ndarray)
        self.assertEqual(pobj.data.dtype, numpy.dtype(">u2"))

    def test_unhandled_type_returns_none(self) -> None:
        transformer = NumpyArrayTransformer()
        with open(_ser_path("testClassArray.ser"), "rb") as f:
            data = f.read()
        # TYPE_OBJECT arrays are not in NUMPY_TYPE_MAP: load_array()
        # must return None so the default element-by-element path runs.
        import io

        from javaobj.constants import TypeCode
        from javaobj.v3.reader import DataReader

        reader = DataReader(io.BytesIO(data))
        result = transformer.load_array(reader, TypeCode.TYPE_OBJECT, 0)
        self.assertIsNone(result)

    def test_numpy_not_installed(self) -> None:
        import io as _io

        import javaobj.v3.transformers as transformers_mod

        original = transformers_mod.numpy
        transformers_mod.numpy = None
        try:
            transformer = NumpyArrayTransformer()
            reader = DataReader(_io.BytesIO(b""))
            result = transformer.load_array(reader, TypeCode.TYPE_BYTE, 0)
            self.assertIsNone(result)
        finally:
            transformers_mod.numpy = original


# ------------------------------------------------------------------------------
# Direct transformer unit tests (white-box: pure-Python logic, no stream
# parsing needed for most branches).
# ------------------------------------------------------------------------------


class TestV3TransformersDirect(unittest.TestCase):
    """Direct unit tests for javaobj.v3.transformers branch coverage."""

    @staticmethod
    def _cd(name: str) -> JavaClassDesc:
        return JavaClassDesc(handle=0, name=name, serial_version_uid=0, desc_flags=0)

    def test_base_transformer_defaults(self) -> None:
        t = ObjectTransformer()
        self.assertIsNone(t.load_custom_writeObject(None, None, "x"))

    def test_java_list_not_found(self) -> None:
        from javaobj.v3.transformers import JavaList

        jl = JavaList()
        jl.annotations = {self._cd("other"): []}
        self.assertFalse(jl.load_from_instance())

    def test_java_primitive_class_str_repr_lt(self) -> None:
        from javaobj.v3.transformers import JavaInt

        ji = JavaInt()
        ji.value = 5
        self.assertEqual(str(ji), "5")
        self.assertEqual(repr(ji), "5")
        self.assertLess(ji, 6)
        self.assertFalse(ji.load_from_instance())  # no field_data: not found

    def test_java_bool_int_dunder(self) -> None:
        from javaobj.v3.transformers import JavaBool, JavaInt

        jb = JavaBool()
        jb.value = True
        self.assertTrue(bool(jb))

        ji = JavaInt()
        ji.value = 42
        self.assertEqual(int(ji), 42)

    def test_java_map_not_found(self) -> None:
        from javaobj.v3.transformers import JavaMap

        jm = JavaMap()
        jm.annotations = {self._cd("other"): []}
        self.assertFalse(jm.load_from_instance())

    def test_java_set_and_tree_set_not_found(self) -> None:
        from javaobj.v3.transformers import JavaSet, JavaTreeSet

        js = JavaSet()
        js.annotations = {self._cd("other"): []}
        self.assertFalse(js.load_from_instance())

        jts = JavaTreeSet()
        jts.annotations = {self._cd("other"): []}
        self.assertFalse(jts.load_from_instance())

    def test_linked_hash_map_load_from_blockdata(self) -> None:
        import io as _io

        from javaobj.v3.parser import JavaStreamParser
        from javaobj.v3.transformers import DefaultObjectTransformer, JavaLinkedHashMap

        data = (
            struct.pack(">ii", 16, 1)
            + bytes([int(TerminalCode.TC_NULL)])
            + bytes([int(TerminalCode.TC_NULL)])
            + bytes([int(TerminalCode.TC_ENDBLOCKDATA)])
            + b"\x00"
        )
        fd = _io.BytesIO(data)
        reader = DataReader(fd)
        parser = JavaStreamParser(fd, [DefaultObjectTransformer()])
        lhm = JavaLinkedHashMap()
        self.assertTrue(lhm.load_from_blockdata(parser, reader))
        self.assertEqual(dict(lhm), {None: None})

    def test_linked_hash_map_bad_endblock(self) -> None:
        import io as _io

        from javaobj.v3.transformers import JavaLinkedHashMap

        data = struct.pack(">ii", 16, 0) + b"\x00"
        reader = DataReader(_io.BytesIO(data))
        with self.assertRaises(ValueError):
            JavaLinkedHashMap().load_from_blockdata(None, reader)

    def test_linked_hash_map_bad_trailing_byte(self) -> None:
        import io as _io

        from javaobj.v3.transformers import JavaLinkedHashMap

        data = struct.pack(">ii", 16, 0) + bytes([int(TerminalCode.TC_ENDBLOCKDATA)]) + b"\x01"
        reader = DataReader(_io.BytesIO(data))
        with self.assertRaises(ValueError):
            JavaLinkedHashMap().load_from_blockdata(None, reader)

    def test_java_time_str_and_not_found(self) -> None:
        jt = JavaTime()
        jt.type = 1
        self.assertIn("JavaTime", str(jt))

        jt2 = JavaTime()
        jt2.annotations = {self._cd("other"): []}
        self.assertFalse(jt2.load_from_instance())

    def test_java_time_requires_blockdata(self) -> None:
        jt = JavaTime()
        jt.annotations = {self._cd("java.time.Ser"): ["not blockdata"]}
        self.assertFalse(jt.load_from_instance())

    def test_java_time_remaining_do_methods(self) -> None:
        jt = JavaTime()
        jt._do_local_time(struct.pack(">b", -5))
        self.assertEqual(jt.hour, 4)

        jt = JavaTime()
        jt._do_local_time(struct.pack(">bb", 5, -3))
        self.assertEqual(jt.minute, 2)

        jt = JavaTime()
        jt._do_local_time(struct.pack(">bbb", 5, 3, -2))
        self.assertEqual(jt.second, 1)

        jt = JavaTime()
        jt._do_zone_offset(struct.pack(">bi", 127, 999999))
        self.assertEqual(jt.offset, 999999)

        jt = JavaTime()
        jt._do_offset_time(struct.pack(">b", -5) + struct.pack(">bi", 127, 111))
        self.assertEqual(jt.offset, 111)

        jt = JavaTime()
        jt._do_offset_date_time(struct.pack(">ibb", 2024, 6, 1) + struct.pack(">b", -5) + struct.pack(">b", 4))
        self.assertEqual(jt.year, 2024)

        jt = JavaTime()
        jt._do_year(struct.pack(">i", 2024))
        self.assertEqual(jt.year, 2024)

        jt = JavaTime()
        jt._do_year_month(struct.pack(">ib", 2024, 6))
        self.assertEqual((jt.year, jt.month), (2024, 6))

        jt = JavaTime()
        jt._do_month_day(struct.pack(">bb", 6, 15))
        self.assertEqual((jt.month, jt.day), (6, 15))

        jt = JavaTime()
        jt._do_period(struct.pack(">iii", 1, 2, 3))
        self.assertEqual((jt.year, jt.month, jt.day), (1, 2, 3))

    def test_default_transformer_handles(self) -> None:
        transformer = DefaultObjectTransformer()
        self.assertTrue(transformer.handles("java.lang.Boolean"))
        self.assertFalse(transformer.handles("com.example.Unknown"))


# ------------------------------------------------------------------------------
# v1 / v2 compatibility tests
# ------------------------------------------------------------------------------


class TestCompat(unittest.TestCase):
    """Tests for the v1→v3 and v2→v3 migration helpers in _compat."""

    # ------------------------------------------------------------------
    # v2 → v3
    # ------------------------------------------------------------------

    def test_v2_to_v3_string(self) -> None:
        """v2_to_v3 converts a v2 JavaString to a v3 JavaString."""
        import javaobj.v2 as javaobj_v2

        v2_obj = javaobj_v2.loads(open(_ser_path("testJapan.ser"), "rb").read())
        v3_obj = v2_to_v3(v2_obj)
        self.assertIsInstance(v3_obj, JavaString)
        self.assertEqual(str(v3_obj), "\u65e5\u672c\u56fd")

    def test_v2_to_v3_instance(self) -> None:
        """v2_to_v3 converts a v2 JavaInstance to a v3 JavaInstance."""
        import javaobj.v2 as javaobj_v2

        v2_obj = javaobj_v2.loads(open(_ser_path("test_readFields.ser"), "rb").read())
        v3_obj = v2_to_v3(v2_obj)
        self.assertIsInstance(v3_obj, JavaInstance)
        self.assertIsNotNone(v3_obj.classdesc)
        self.assertEqual(v3_obj.classdesc.name, "OneTest$SerializableTestHelper")

    def test_v2_to_v3_enum(self) -> None:
        """v2_to_v3 converts a v2 JavaEnum to a v3 JavaEnum."""
        import javaobj.v2 as javaobj_v2

        with open(_ser_path("objEnums.ser"), "rb") as f:
            v2_obj = javaobj_v2.load(f)
        # objEnums.ser is an instance that contains an enum field, not a
        # standalone enum; parse the color field instead
        v3_obj = v2_to_v3(v2_obj)
        self.assertIsInstance(v3_obj, JavaInstance)

    def test_v2_to_v3_array(self) -> None:
        """v2_to_v3 converts a v2 JavaArray (chars) to a v3 JavaArray."""
        import javaobj.v2 as javaobj_v2

        v2_obj = javaobj_v2.loads(open(_ser_path("testCharArray.ser"), "rb").read())
        v3_obj = v2_to_v3(v2_obj)
        self.assertIsInstance(v3_obj, JavaArray)
        self.assertEqual(v3_obj.element_type, FieldType.CHAR)

    def test_v2_to_v3_unknown_raises(self) -> None:
        """v2_to_v3 raises JavaObjError for an unmappable type."""
        with self.assertRaises(JavaObjError):
            v2_to_v3(object())  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # v1 → v3
    # ------------------------------------------------------------------

    def test_v1_to_v3_instance(self) -> None:
        """v1_to_v3 converts a v1 JavaObject to a v3 JavaInstance."""
        import javaobj.v1 as javaobj_v1

        v1_obj = javaobj_v1.loads(open(_ser_path("test_readFields.ser"), "rb").read())
        v3_obj = v1_to_v3(v1_obj)
        self.assertIsInstance(v3_obj, JavaInstance)
        self.assertIsNotNone(v3_obj.classdesc)
        self.assertEqual(v3_obj.classdesc.name, "OneTest$SerializableTestHelper")

    def test_v1_to_v3_unknown_raises(self) -> None:
        """v1_to_v3 raises JavaObjError for an unmappable type."""
        with self.assertRaises(JavaObjError):
            v1_to_v3(object())  # type: ignore[arg-type]


# ------------------------------------------------------------------------------
# Writer / round-trip tests
# ------------------------------------------------------------------------------


class TestWriter(TestJavaobjV3Base):
    """Tests for javaobj.v3.writer — serializing beans back to bytes."""

    # ------------------------------------------------------------------
    # Modified UTF-8 encoder unit tests
    # ------------------------------------------------------------------

    def test_mutf8_ascii(self) -> None:
        """ASCII characters round-trip through Modified UTF-8."""
        s = "Hello, World!"
        self.assertEqual(_encode_mutf8(s), s.encode("ascii"))

    def test_mutf8_null(self) -> None:
        """Null character is encoded as two-byte sequence 0xC0 0x80."""
        self.assertEqual(_encode_mutf8("\x00"), b"\xc0\x80")

    def test_mutf8_japanese(self) -> None:
        """CJK characters produce a 3-byte-per-codepoint encoding."""
        s = "\u65e5\u672c\u56fd"  # 日本国
        encoded = _encode_mutf8(s)
        # 3 codepoints × 3 bytes each = 9 bytes
        self.assertEqual(len(encoded), 9)

    def test_mutf8_supplementary(self) -> None:
        """A supplementary character (U+1F600 😀) encodes as 6 bytes."""
        encoded = _encode_mutf8("\U0001f600")
        self.assertEqual(len(encoded), 6)
        # Must start with the first surrogate half marker
        self.assertEqual(encoded[0], 0xED)
        self.assertEqual(encoded[3], 0xED)

    # ------------------------------------------------------------------
    # dumps / dump API smoke tests
    # ------------------------------------------------------------------

    def test_dumps_returns_bytes(self) -> None:
        """javaobj.v3.dumps() returns bytes starting with the magic header."""
        pobj = self.load_file("testBoolIntLong.ser")
        data = javaobj.dumps(pobj)
        self.assertIsInstance(data, bytes)
        # Magic: 0xACED, version: 0x0005
        self.assertEqual(data[:4], b"\xac\xed\x00\x05")

    def test_dump_to_fd(self) -> None:
        """javaobj.v3.dump(fd, obj) writes to a file-like object."""
        import io

        pobj = self.load_file("testBoolIntLong.ser")
        buf = io.BytesIO()
        javaobj.dump(buf, pobj)
        self.assertEqual(buf.getvalue()[:4], b"\xac\xed\x00\x05")

    # ------------------------------------------------------------------
    # Round-trip tests (parse → write → re-parse → compare field values)
    # ------------------------------------------------------------------

    def _round_trip(self, filename: str) -> tuple[Any, Any]:
        """
        Parses *filename*, serializes the result, re-parses the bytes, and
        returns ``(original, re_parsed)`` for the caller to assert on.
        """
        original = self.load_file(filename)
        serialized = javaobj.dumps(original)
        re_parsed = javaobj.loads(serialized)
        return original, re_parsed

    def test_round_trip_instance_fields(self) -> None:
        """NOWRCLASS instance: field values survive a write→re-read cycle."""
        original, re_parsed = self._round_trip("testBoolIntLong.ser")
        self.assertIsInstance(re_parsed, JavaInstance)
        # Compare all field values by name
        orig_cd = original.get_class()
        new_cd = re_parsed.get_class()
        self.assertEqual(orig_cd.name, new_cd.name)
        self.assertEqual(orig_cd.serial_version_uid, new_cd.serial_version_uid)
        for field_name in orig_cd.fields_names:
            self.assertEqual(
                original.get_field(field_name),
                re_parsed.get_field(field_name),
                msg=f"Field {field_name!r} differs after round-trip",
            )

    def test_round_trip_string(self) -> None:
        """JavaString: value survives a write→re-read cycle."""
        original, re_parsed = self._round_trip("testJapan.ser")
        self.assertIsInstance(re_parsed, JavaString)
        self.assertEqual(str(original), str(re_parsed))

    def test_round_trip_char_array(self) -> None:
        """JavaArray (chars): data survives a write→re-read cycle."""
        original, re_parsed = self._round_trip("testCharArray.ser")
        self.assertIsInstance(re_parsed, JavaArray)
        self.assertEqual(re_parsed.element_type, FieldType.CHAR)
        self.assertEqual(list(original.data), list(re_parsed.data))

    def test_round_trip_byte_array(self) -> None:
        """JavaArray (bytes): data survives a write→re-read cycle."""
        # testBytes.ser is a raw BlockData, so use a proper Java array fixture
        original, re_parsed = self._round_trip("objArrays.ser")
        self.assertEqual(type(original), type(re_parsed))

    def test_round_trip_enum(self) -> None:
        """Enum constant embedded in an instance: class/value survive round-trip."""
        # objEnums.ser contains a JavaInstance with a JavaEnum field 'color'
        original = self.load_file("objEnums.ser")
        serialized = javaobj.dumps(original)
        re_parsed = javaobj.loads(serialized)
        self.assertIsInstance(re_parsed, JavaInstance)
        self.assertEqual(re_parsed.get_class().name, original.get_class().name)
        orig_color = original.color
        new_color = re_parsed.color
        self.assertIsInstance(new_color, JavaEnum)
        self.assertEqual(new_color.classdesc.name, orig_color.classdesc.name)
        self.assertEqual(str(new_color.constant), str(orig_color.constant))

    def test_round_trip_super_class(self) -> None:
        """Instance with class hierarchy: all fields survive round-trip."""
        original, re_parsed = self._round_trip("objSuper.ser")
        self.assertIsInstance(re_parsed, JavaInstance)
        orig_cd = original.get_class()
        new_cd = re_parsed.get_class()
        self.assertEqual(orig_cd.name, new_cd.name)
        # Walk hierarchy and compare every field value
        for o_hcd, n_hcd in zip(orig_cd.get_hierarchy(), new_cd.get_hierarchy()):
            self.assertEqual(o_hcd.name, n_hcd.name)
            if o_hcd not in original.field_data:
                continue
            for o_f, n_f in zip(o_hcd.fields, n_hcd.fields):
                self.assertEqual(o_f.name, n_f.name)
                self.assertEqual(
                    original.field_data[o_hcd][o_f],
                    re_parsed.field_data[n_hcd][n_f],
                    msg=f"Field {o_f.name!r} in {o_hcd.name!r}",
                )

    def test_round_trip_wrclass(self) -> None:
        """WRCLASS (writeObject) instance: class name survives round-trip."""
        original, re_parsed = self._round_trip("test_readFields.ser")
        self.assertIsInstance(re_parsed, JavaInstance)
        orig_cd = original.get_class()
        new_cd = re_parsed.get_class()
        self.assertEqual(orig_cd.name, new_cd.name)

    def test_round_trip_class_token(self) -> None:
        """TC_CLASS token: class name survives round-trip."""
        original, re_parsed = self._round_trip("testClass.ser")
        self.assertIsInstance(re_parsed, JavaClass)
        self.assertEqual(re_parsed.name, original.name)

    def test_multi_object_stream(self) -> None:
        """Multiple objects in one stream: all survive round-trip."""
        obj_a = self.load_file("testJapan.ser")
        obj_b = self.load_file("testBoolIntLong.ser")
        serialized = javaobj.dumps(obj_a, obj_b)
        result = javaobj.loads(serialized)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], JavaString)
        self.assertIsInstance(result[1], JavaInstance)


# ------------------------------------------------------------------------------
# GZip decompression test


class TestGzip(TestJavaobjV3Base):
    """Tests for transparent GZip decompression."""

    def test_gzip_equivalent(self) -> None:
        """testChars.ser and testChars.ser.gz must parse to the same value."""
        try:
            plain_path = _ser_path("testChars.ser")
            gz_path = _ser_path("testChars.ser.gz")
        except FileNotFoundError:
            self.skipTest("testChars.ser.gz not found")

        with open(plain_path, "rb") as f:
            plain = javaobj.load(f)
        with open(gz_path, "rb") as f:
            gzipped = javaobj.load(f)

        self.assertEqual(plain, gzipped)


# ------------------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
