#!/usr/bin/env python
# -- Content-Encoding: utf-8 --
"""
Direct unit tests for javaobj.modifiedutf8 (Java Modified UTF-8 codec).

These target the decoder's error paths and edge cases that the
higher-level v1/v2/v3 parser tests never exercise, since the fixtures
they use only contain well-formed, mostly-ASCII strings.

Compatible with Python 2.7 and 3.4+ (this module is shared by v1/v2/v3).

:authors: Thomas Calmant
:license: Apache License 2.0
"""

from __future__ import unicode_literals

# Standard library
import os
import sys
import unittest

# Make sure javaobj is importable when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Javaobj
from javaobj.modifiedutf8 import (  # noqa: E402
    DECODE_MAP,
    byte_to_int,
    decode_modified_utf8,
    decoder,
)

# ------------------------------------------------------------------------------


def _b(*ints):
    """Builds a byte string from a list of ints (Python 2/3 compatible)."""
    return bytes(bytearray(ints))


# ------------------------------------------------------------------------------


class TestByteToInt(unittest.TestCase):
    """Tests for the byte_to_int() helper."""

    def test_int_passthrough(self):
        self.assertEqual(byte_to_int(65), 65)

    def test_single_byte(self):
        self.assertEqual(byte_to_int(b"A"), 65)

    def test_invalid_type(self):
        with self.assertRaises(ValueError):
            byte_to_int(3.14)

    def test_invalid_type_list(self):
        with self.assertRaises(ValueError):
            byte_to_int([1, 2, 3])


# ------------------------------------------------------------------------------


class TestDecodeMap(unittest.TestCase):
    """Tests for the DecodeMap helper class."""

    def test_apply_success(self):
        dm = DECODE_MAP[2][0]
        # 0x80 masked with 0xC0 == 0x80 -> matches, bits merged in
        value = dm.apply(0x80, 0x01, b"\xc0\x80", 0, 1)
        self.assertEqual(value, (0x01 << 6) | 0)

    def test_apply_mismatch_raises(self):
        dm = DECODE_MAP[2][0]
        with self.assertRaises(UnicodeDecodeError):
            dm.apply(0x00, 0x01, b"\xc0\x00", 0, 1)

    def test_repr(self):
        dm = DECODE_MAP[2][0]
        text = repr(dm)
        self.assertIn("DecodeMap(", text)
        self.assertIn("count=", text)


# ------------------------------------------------------------------------------


class TestDecoder(unittest.TestCase):
    """Tests for the low-level decoder() generator."""

    def test_ascii(self):
        self.assertEqual(list(decoder(_b(0x41, 0x42))), ["A", "B"])

    def test_embedded_zero_byte(self):
        with self.assertRaises(UnicodeDecodeError):
            list(decoder(_b(0x00)))

    def test_misplaced_continuation(self):
        # 0x80 = 10000000, a continuation byte with no lead byte
        with self.assertRaises(UnicodeDecodeError):
            list(decoder(_b(0x80)))

    def test_invalid_encoding_character(self):
        # 0xF8 = 11111000, matches the "1111xxxx" invalid branch
        with self.assertRaises(UnicodeDecodeError):
            list(decoder(_b(0xF8)))

    def test_two_byte_sequence_success(self):
        # U+00E9 'e with acute accent' encoded as 0xC3 0xA9
        self.assertEqual(list(decoder(_b(0xC3, 0xA9))), ["é"])

    def test_two_byte_sequence_incomplete(self):
        # Lead byte with nothing following
        with self.assertRaises(UnicodeDecodeError):
            list(decoder(_b(0xC3)))

    def test_two_byte_sequence_invalid_continuation(self):
        # Second byte doesn't match the 10xxxxxx continuation mask
        with self.assertRaises(UnicodeDecodeError):
            list(decoder(_b(0xC3, 0x00)))

    def test_three_byte_sequence_success(self):
        # U+3042 (Hiragana A) encoded as 0xE3 0x81 0x82
        self.assertEqual(list(decoder(_b(0xE3, 0x81, 0x82))), ["あ"])

    def test_three_byte_sequence_incomplete(self):
        with self.assertRaises(UnicodeDecodeError):
            list(decoder(_b(0xE3, 0x81)))

    def test_surrogate_pair_success(self):
        # U+1F600 (an emoji) encoded as a CESU-8/Modified-UTF-8 surrogate
        # pair: two 3-byte sequences (0xED-led) encoding the UTF-16
        # surrogate pair 0xD83D 0xDE00.
        encoded = _b(0xED, 0xA0, 0xBD, 0xED, 0xB8, 0x80)
        decoded = "".join(decoder(encoded))
        self.assertEqual(decoded, "\U0001F600")

    def test_surrogate_pair_incomplete(self):
        with self.assertRaises(UnicodeDecodeError):
            list(decoder(_b(0xED, 0xA0)))


# ------------------------------------------------------------------------------


class TestDecodeModifiedUtf8(unittest.TestCase):
    """Tests for the decode_modified_utf8() public function."""

    def test_strict_raises(self):
        with self.assertRaises(UnicodeDecodeError):
            decode_modified_utf8(b"\x00")

    def test_errors_ignore(self):
        # The underlying generator is closed by the raised error, so
        # decoding stops there: only the bytes read before the bad byte
        # are returned.
        value, length = decode_modified_utf8(b"A\x00B", errors="ignore")
        self.assertEqual(value, "A")
        self.assertEqual(length, 1)

    def test_errors_replace(self):
        value, length = decode_modified_utf8(b"A\x00B", errors="replace")
        self.assertEqual(value, "A�")
        self.assertEqual(length, 2)

    def test_valid_ascii(self):
        value, length = decode_modified_utf8(b"hello")
        self.assertEqual(value, "hello")
        self.assertEqual(length, 5)


# ------------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
