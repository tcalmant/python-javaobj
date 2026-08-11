#!/usr/bin/env python
# -- Content-Encoding: utf-8 --
"""
Direct unit tests for javaobj.utils (logging helpers, bytes/str
converters, gzip auto-detection, hex dump).

Compatible with Python 2.7 and 3.4+ (this module is shared by v1/v2/v3).

Note: plain string literals below are deliberately left as the
*native* ``str`` type for the running interpreter (bytes on Python 2,
text on Python 3) rather than forced to unicode, since to_str()/
to_unicode() behave differently based on the native str type of each
Python version -- that is exactly what is under test here.

:authors: Thomas Calmant
:license: Apache License 2.0
"""

# Standard library
import gzip
import io
import os
import sys
import unittest

# Make sure javaobj is importable when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Javaobj
from javaobj.utils import (  # noqa: E402
    java_data_fd,
    hexdump,
    read_string,
    read_struct,
    to_bytes,
    to_str,
    to_unicode,
)

# ------------------------------------------------------------------------------


class TestStrConversion(unittest.TestCase):
    """Tests for to_str / to_unicode / to_bytes."""

    def test_to_str_already_str(self):
        # Early-return branch: input is already the native str type
        value = "already a string"
        self.assertIs(to_str(value), value)

    def test_to_unicode_already_unicode(self):
        # Early-return branch: input is already unicode text
        value = u"already unicode"
        self.assertIs(to_unicode(value), value)

    def test_to_str_valid_utf8(self):
        self.assertEqual(to_str(b"hello"), "hello")

    def test_to_unicode_modified_utf8_fallback(self):
        # 0xC0 0x80 is an overlong encoding of NUL: invalid standard
        # UTF-8, but valid Modified UTF-8 -> falls back to the
        # decode_modified_utf8() codec.
        self.assertEqual(to_unicode(b"\xc0\x80"), u"\x00")

    def test_to_bytes_from_str(self):
        self.assertEqual(to_bytes("hello"), b"hello")

    def test_to_bytes_already_bytes(self):
        value = b"already bytes"
        self.assertIs(to_bytes(value), value)


# ------------------------------------------------------------------------------


class TestReadHelpers(unittest.TestCase):
    """Tests for read_struct / read_string."""

    def test_read_struct(self):
        (value,), remaining = read_struct(b"\x00\x2a\xff\xff", ">H")
        self.assertEqual(value, 42)
        self.assertEqual(remaining, b"\xff\xff")

    def test_read_string(self):
        data = b"\x00\x05hello\x00\x00extra"
        value, remaining = read_string(data)
        self.assertEqual(value, u"hello")
        self.assertEqual(remaining, b"\x00\x00extra")


# ------------------------------------------------------------------------------


class TestJavaDataFd(unittest.TestCase):
    """Tests for java_data_fd() GZip auto-detection."""

    def test_raw_stream_passthrough(self):
        raw = io.BytesIO(b"\xac\xed\x00\x05rest")
        fd = java_data_fd(raw)
        self.assertIs(fd, raw)
        self.assertEqual(fd.read(2), b"\xac\xed")

    def test_gzip_stream_unwrapped(self):
        buf = io.BytesIO()
        gz = gzip.GzipFile(fileobj=buf, mode="wb")
        try:
            gz.write(b"\xac\xed\x00\x05rest")
        finally:
            gz.close()
        buf.seek(0)
        fd = java_data_fd(buf)
        self.assertIsInstance(fd, gzip.GzipFile)
        self.assertEqual(fd.read(4), b"\xac\xed\x00\x05")

    def test_unrecognized_header_passthrough(self):
        raw = io.BytesIO(b"\x00\x00garbage")
        fd = java_data_fd(raw)
        self.assertIs(fd, raw)
        self.assertEqual(fd.read(2), b"\x00\x00")


# ------------------------------------------------------------------------------


class TestHexdump(unittest.TestCase):
    """Tests for hexdump()."""

    def test_hexdump_contains_offset_and_hex(self):
        text = hexdump(b"ABC")
        self.assertIn("0000", text)
        self.assertIn("41 42 43", text)
        self.assertIn("ABC", text)


# ------------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
