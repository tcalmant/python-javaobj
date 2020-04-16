#!/usr/bin/python
# -- Content-Encoding: utf-8 --
"""
Provides utility methods used by the core implementation of javaobj.

Namely: logging methods, bytes/str/unicode converters

:authors: Thomas Calmant
:license: Apache License 2.0
:version: 0.4.1
:status: Alpha

..

    Copyright 2020 Thomas Calmant

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

from __future__ import absolute_import

# Standard library
from typing import Any, Tuple
import logging
import struct
import sys

# Modified UTF-8 parser
from .modifiedutf8 import decode_modified_utf8

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 4, 1)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------

# Setup the logger
_log = logging.getLogger("javaobj")


def log_debug(message, ident=0):
    """
    Logs a message at debug level

    :param message: Message to log
    :param ident: Number of indentation spaces
    """
    _log.debug("%s%s", " " * (ident * 2), message)


def log_error(message, ident=0):
    """
    Logs a message at error level

    :param message: Message to log
    :param ident: Number of indentation spaces
    """
    _log.error("%s%s", " " * (ident * 2), message)


# ------------------------------------------------------------------------------


def read_struct(data, fmt_str):
    # type: (bytes, str) -> Tuple
    """
    Reads input bytes and extract the given structure. Returns both the read
    elements and the remaining data

    :param data: Data as bytes
    :param fmt_str: Struct unpack format string
    :return: A tuple (results as tuple, remaining data)
    """
    size = struct.calcsize(fmt_str)
    return struct.unpack(fmt_str, data[:size]), data[size:]


def read_string(data, length_fmt="H"):
    # type: (bytes, str) -> Tuple[UNICODE_TYPE, bytes]
    """
    Reads a serialized string

    :param data: Bytes where to read the string from
    :param length_fmt: Structure format of the string length (H or Q)
    :return: The deserialized string
    """
    (length,), data = read_struct(data, ">{0}".format(length_fmt))
    ba, data = data[:length], data[length:]
    return to_unicode(ba), data


# ------------------------------------------------------------------------------


def hexdump(src, start_offset=0, length=16):
    # type: (str, int, int) -> str
    """
    Prepares an hexadecimal dump string

    :param src: A string containing binary data
    :param start_offset: The start offset of the source
    :param length: Length of a dump line
    :return: A dump string
    """
    FILTER = "".join(
        (len(repr(chr(x))) == 3) and chr(x) or "." for x in range(256)
    )
    pattern = "{{0:04X}}   {{1:<{0}}}  {{2}}\n".format(length * 3)

    # Convert raw data to str (Python 3 compatibility)
    src = to_str(src, "latin-1")

    result = []
    for i in range(0, len(src), length):
        s = src[i : i + length]
        hexa = " ".join("{0:02X}".format(ord(x)) for x in s)
        printable = s.translate(FILTER)
        result.append(pattern.format(i + start_offset, hexa, printable))

    return "".join(result)


# ------------------------------------------------------------------------------


if sys.version_info[0] >= 3:
    BYTES_TYPE = bytes
    UNICODE_TYPE = str
    unicode_char = chr

    def bytes_char(c):
        return bytes((c,))

    # Python 3 interpreter : bytes & str
    def to_bytes(data, encoding="UTF-8"):
        """
        Converts the given string to an array of bytes.
        Returns the first parameter if it is already an array of bytes.

        :param data: A unicode string
        :param encoding: The encoding of data
        :return: The corresponding array of bytes
        """
        if type(data) is bytes:
            # Nothing to do
            return data
        return data.encode(encoding)

    def to_str(data, encoding="UTF-8"):
        """
        Converts the given parameter to a string.
        Returns the first parameter if it is already an instance of ``str``.

        :param data: A string
        :param encoding: The encoding of data
        :return: The corresponding string
        """
        if type(data) is str:
            # Nothing to do
            return data
        try:
            return str(data, encoding)
        except UnicodeDecodeError:
            return decode_modified_utf8(data)[0]

    # Same operation
    to_unicode = to_str

    def read_to_str(data):
        """
        Concats all bytes into a string
        """
        return "".join(chr(char) for char in data)


else:
    BYTES_TYPE = str
    UNICODE_TYPE = unicode  # pylint:disable=undefined-variable
    unicode_char = unichr  # pylint:disable=undefined-variable
    bytes_char = chr

    # Python 2 interpreter : str & unicode
    def to_str(data, encoding="UTF-8"):
        """
        Converts the given parameter to a string.
        Returns the first parameter if it is already an instance of ``str``.

        :param data: A string
        :param encoding: The encoding of data
        :return: The corresponding string
        """
        if type(data) is str:
            # Nothing to do
            return data
        return data.encode(encoding)

    # Same operation
    to_bytes = to_str

    # Python 2 interpreter : str & unicode
    def to_unicode(data, encoding="UTF-8"):
        """
        Converts the given parameter to a string.
        Returns the first parameter if it is already an instance of ``str``.

        :param data: A string
        :param encoding: The encoding of data
        :return: The corresponding string
        """
        if type(data) is UNICODE_TYPE:
            # Nothing to do
            return data
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            return decode_modified_utf8(data)[0]

    def read_to_str(data):
        """
        Nothing to do in Python 2
        """
        return data
