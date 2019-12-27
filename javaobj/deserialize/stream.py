#!/usr/bin/env python3
"""
Utility module to handle streams like in Java
"""

from typing import Any, IO, List
import struct

from ..modifiedutf8 import decode_modified_utf8


class DataStreamReader:
    """
    Reads the given file object with object input stream-like methods
    """

    def __init__(self, fd: IO[bytes]):
        """
        :param fd: The input stream
        """
        self.__fd = fd

    def read(self, struct_format: str) -> List[Any]:
        """
        Reads from the input stream, using struct

        :param struct_format: An unpack format string
        :return: The result of struct.unpack (tuple)
        :raise EOFError: End of stream reached during unpacking
        """
        length = struct.calcsize(struct_format)
        bytes_array = self.__fd.read(length)

        if len(bytes_array) != length:
            raise EOFError("Stream has ended unexpectedly while parsing.")

        return struct.unpack(struct_format, bytes_array)

    def read_bool(self) -> bool:
        """
        Shortcut to read a single `boolean` (1 byte)
        """
        return bool(self.read(">B")[0])

    def read_byte(self) -> int:
        """
        Shortcut to read a single `byte` (1 byte)
        """
        return self.read(">b")[0]

    def read_ubyte(self) -> int:
        """
        Shortcut to read an unsigned `byte` (1 byte)
        """
        return self.read(">B")[0]

    def read_char(self) -> chr:
        """
        Shortcut to read a single `char` (2 bytes)
        """
        return chr(self.read(">H")[0])

    def read_short(self) -> int:
        """
        Shortcut to read a single `short` (2 bytes)
        """
        return self.read(">h")[0]

    def read_ushort(self) -> int:
        """
        Shortcut to read an unsigned `short` (2 bytes)
        """
        return self.read(">H")[0]

    def read_int(self) -> int:
        """
        Shortcut to read a single `int` (4 bytes)
        """
        return self.read(">i")[0]

    def read_float(self) -> float:
        """
        Shortcut to read a single `float` (4 bytes)
        """
        return self.read(">f")[0]

    def read_long(self) -> int:
        """
        Shortcut to read a single `long` (8 bytes)
        """
        return self.read(">q")[0]

    def read_double(self) -> float:
        """
        Shortcut to read a single `double` (8 bytes)
        """
        return self.read(">d")[0]

    def read_UTF(self) -> str:
        """
        Reads a Java string
        """
        length = self.read_ushort()
        ba = self.__fd.read(length)
        return decode_modified_utf8(ba)[0]
