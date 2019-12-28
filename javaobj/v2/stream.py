#!/usr/bin/env python3
"""
Utility module to handle streams like in Java

:authors: Thomas Calmant
:license: Apache License 2.0
:version: 0.4.0
:status: Alpha

..

    Copyright 2019 Thomas Calmant

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

from typing import Any, IO, List
import struct

from ..modifiedutf8 import decode_modified_utf8


class DataStreamReader:
    """
    Reads the given file object with object input stream-like methods
    """

    def __init__(self, fd):
        # type: (IO[bytes]) -> None
        """
        :param fd: The input stream
        """
        self.__fd = fd

    def read(self, struct_format):
        # type: (str) -> List[Any]
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

    def read_bool(self):
        # type: () -> bool
        """
        Shortcut to read a single `boolean` (1 byte)
        """
        return bool(self.read(">B")[0])

    def read_byte(self):
        # type: () -> int
        """
        Shortcut to read a single `byte` (1 byte)
        """
        return self.read(">b")[0]

    def read_ubyte(self):
        # type: () -> int
        """
        Shortcut to read an unsigned `byte` (1 byte)
        """
        return self.read(">B")[0]

    def read_char(self):
        # type: () -> chr
        """
        Shortcut to read a single `char` (2 bytes)
        """
        return chr(self.read(">H")[0])

    def read_short(self):
        # type: () -> int
        """
        Shortcut to read a single `short` (2 bytes)
        """
        return self.read(">h")[0]

    def read_ushort(self):
        # type: () -> int
        """
        Shortcut to read an unsigned `short` (2 bytes)
        """
        return self.read(">H")[0]

    def read_int(self):
        # type: () -> int
        """
        Shortcut to read a single `int` (4 bytes)
        """
        return self.read(">i")[0]

    def read_float(self):
        # type: () -> float
        """
        Shortcut to read a single `float` (4 bytes)
        """
        return self.read(">f")[0]

    def read_long(self):
        # type: () -> int
        """
        Shortcut to read a single `long` (8 bytes)
        """
        return self.read(">q")[0]

    def read_double(self):
        # type: () -> float
        """
        Shortcut to read a single `double` (8 bytes)
        """
        return self.read(">d")[0]

    def read_UTF(self):
        # type: () -> str
        """
        Reads a Java string
        """
        length = self.read_ushort()
        ba = self.__fd.read(length)
        return decode_modified_utf8(ba)[0]
