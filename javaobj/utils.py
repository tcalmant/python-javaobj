#!/usr/bin/python
# -- Content-Encoding: utf-8 --
"""
Provides utility methods used by the core implementation of javaobj.

Namely: logging methods, bytes/str/unicode converters

:authors: Thomas Calmant
:license: Apache License 2.0
:version: 0.3.0
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

# Standard library
import logging
import sys

# Modified UTF-8 parser
from javaobj.modifiedutf8 import decode_modified_utf8

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 3, 0)
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

if sys.version_info[0] >= 3:
    UNICODE_TYPE = str
    unicode_char = chr

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
    UNICODE_TYPE = unicode
    unicode_char = unichr

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
        if type(data) is unicode:
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
