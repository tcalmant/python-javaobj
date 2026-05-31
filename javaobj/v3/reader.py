#!/usr/bin/env python3
"""
Low-level typed binary reader for the Java Object Serialization stream format

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
import struct
from typing import IO

# Javaobj
from ..modifiedutf8 import decode_modified_utf8
from .exceptions import ParseError

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 5, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------

__all__ = ["DataReader"]


class DataReader:
    """
    Typed binary stream reader for the Java Object Serialization protocol.

    The reader tracks the current stream offset so that :class:`ParseError`
    messages can always pinpoint the exact location of a problem.

    Safety limits prevent allocation attacks:

    * ``max_array_size`` – maximum number of bytes that a single array or
      bulk-read operation may allocate (default 100 MiB).
    * ``max_string_size`` – maximum byte length accepted for TC_LONGSTRING
      payloads (default 100 MiB).  Normal TC_STRING payloads are limited to
      65 535 bytes by the 2-byte length field.
    """

    __slots__ = ("_fd", "_offset", "_max_array_size", "_max_string_size")

    #: Default limit on a single array allocation (100 MiB).
    DEFAULT_MAX_ARRAY_SIZE: int = 100 * 1024 * 1024

    #: Default recursion depth limit for the parser (not enforced here but
    #: stored as a convenience constant used by :class:`JavaStreamParser`).
    DEFAULT_MAX_DEPTH: int = 500

    #: Default limit for TC_LONGSTRING payloads (100 MiB).
    DEFAULT_MAX_STRING_SIZE: int = 100 * 1024 * 1024

    def __init__(
        self,
        fd: IO[bytes],
        *,
        max_array_size: int = DEFAULT_MAX_ARRAY_SIZE,
        max_string_size: int = DEFAULT_MAX_STRING_SIZE,
    ) -> None:
        """
        :param fd: A readable binary file-like object.
        :param max_array_size: Maximum bytes for bulk array reads.
        :param max_string_size: Maximum bytes for TC_LONGSTRING payloads.
        """
        self._fd = fd
        self._offset: int = 0
        self._max_array_size = max_array_size
        self._max_string_size = max_string_size

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def offset(self) -> int:
        """Current byte offset in the stream (read-only)."""
        return self._offset

    # ------------------------------------------------------------------
    # Raw I/O
    # ------------------------------------------------------------------

    def read_bytes(self, n: int) -> bytes:
        """
        Reads exactly *n* bytes from the stream.

        :raises EOFError: If fewer than *n* bytes are available.
        """
        data = self._fd.read(n)
        if len(data) != n:
            raise EOFError(
                f"Unexpected end of stream: expected {n} bytes, got {len(data)} at offset 0x{self._offset:x}"
            )
        self._offset += n
        return data

    def read_struct(self, fmt: str) -> tuple:
        """
        Reads and unpacks a :mod:`struct` format string.

        :param fmt: A struct format string (e.g. ``">i"`` for big-endian int).
        :return: The unpacked tuple of values.
        """
        size = struct.calcsize(fmt)
        data = self.read_bytes(size)
        return struct.unpack(fmt, data)

    # ------------------------------------------------------------------
    # Java primitive types
    # ------------------------------------------------------------------

    def read_bool(self) -> bool:
        """Reads a Java ``boolean`` (1 byte)."""
        return bool(self.read_struct(">B")[0])

    def read_byte(self) -> int:
        """Reads a Java signed ``byte`` (1 byte, -128 … 127)."""
        return self.read_struct(">b")[0]

    def read_ubyte(self) -> int:
        """Reads an unsigned byte (1 byte, 0 … 255)."""
        return self.read_struct(">B")[0]

    def read_short(self) -> int:
        """Reads a Java ``short`` (2 bytes, signed)."""
        return self.read_struct(">h")[0]

    def read_ushort(self) -> int:
        """Reads an unsigned ``short`` (2 bytes)."""
        return self.read_struct(">H")[0]

    def read_int(self) -> int:
        """Reads a Java ``int`` (4 bytes, signed)."""
        return self.read_struct(">i")[0]

    def read_long(self) -> int:
        """Reads a Java ``long`` (8 bytes, signed)."""
        return self.read_struct(">q")[0]

    def read_float(self) -> float:
        """Reads a Java ``float`` (4 bytes, IEEE 754 single-precision)."""
        return self.read_struct(">f")[0]

    def read_double(self) -> float:
        """Reads a Java ``double`` (8 bytes, IEEE 754 double-precision)."""
        return self.read_struct(">d")[0]

    def read_char(self) -> str:
        """
        Reads a Java ``char`` (2 bytes, unsigned UTF-16 code unit) and returns
        the corresponding Python :class:`str` character.
        """
        return chr(self.read_struct(">H")[0])

    # ------------------------------------------------------------------
    # Java string types (Modified UTF-8)
    # ------------------------------------------------------------------

    def read_utf(self) -> str:
        """
        Reads a Java ``UTF`` string: 2-byte unsigned length followed by
        Modified UTF-8 encoded bytes.
        """
        length = self.read_ushort()
        return self._read_mutf8(length)

    def read_long_utf(self) -> str:
        """
        Reads a Java long ``UTF`` string: 8-byte signed length followed by
        Modified UTF-8 encoded bytes.

        :raises ParseError: If the declared length exceeds ``max_string_size``
                            or is negative.
        """
        length = self.read_long()
        if length < 0 or length > self._max_string_size:
            raise ParseError(
                f"TC_LONGSTRING: invalid length {length} (limit is {self._max_string_size} bytes)",
                self._offset,
            )
        return self._read_mutf8(length)

    def _read_mutf8(self, length: int) -> str:
        """
        Decodes *length* raw bytes as Modified UTF-8.

        :param length: Number of bytes to read from the stream.
        :return: The decoded Python :class:`str`.
        :raises ParseError: If the bytes cannot be decoded.
        """
        data = self.read_bytes(length)
        try:
            value, _ = decode_modified_utf8(data)
        except UnicodeDecodeError as exc:
            raise ParseError(
                f"Modified UTF-8 decoding failed: {exc}",
                self._offset - length,
            ) from exc
        return value
