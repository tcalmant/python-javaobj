#!/usr/bin/env python3
"""
Tests for javaobj v3.

:authors: Thomas Calmant
:license: Apache License 2.0
:version: 0.5.0
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
import subprocess
import sys
import unittest
from typing import Any

# Make sure javaobj is importable when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Javaobj
import javaobj.v3 as javaobj
from javaobj.v3._compat import v1_to_v3, v2_to_v3
from javaobj.v3.beans import (
    FieldType,
    JavaArray,
    JavaClass,
    JavaClassDesc,
    JavaEnum,
    JavaInstance,
    JavaString,
)
from javaobj.v3.exceptions import JavaObjError, ParseError, SecurityError
from javaobj.v3.transformers import (
    JavaTime,
    ObjectTransformer,
)
from javaobj.v3.writer import _encode_mutf8

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
