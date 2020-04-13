#!/usr/bin/env python3
"""
Definition of the object transformer API

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

from __future__ import absolute_import

from typing import Optional

from .beans import JavaClassDesc, JavaInstance
from .stream import DataStreamReader
from ..constants import TypeCode

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 4, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------


class ObjectTransformer:
    """
    Representation of an object transformer
    """

    def create_instance(self, classdesc):
        # type: (JavaClassDesc) -> Optional[JavaInstance]
        """
        Transforms a parsed Java object into a Python object.

        The result must be a JavaInstance bean, or None if the transformer
        doesn't support this kind of instance.

        :param classdesc: The description of a Java class
        :return: The Python form of the object, or the original JavaObject
        """
        return None

    def load_array(self, reader, type_code, size):
        # type: (DataStreamReader, TypeCode, int) -> Optional[list]
        """
        Loads and returns the content of a Java array, if possible.

        The result of this method must be the content of the array, i.e. a list
        or an array. It will be stored in a JavaArray bean created by the
        parser.

        This method must return None if it can't handle the array.

        :param reader: The data stream reader
        :param type_code: Type of the elements of the array
        :param size: Number of elements in the array
        """
        return None

    def load_custom_writeObject(self, parser, reader, name):
        """
        Reads content stored from a custom writeObject.

        This method is called only if the class description has both the
        ``SC_SERIALIZABLE`` and ``SC_WRITE_METHOD`` flags set.

        The stream parsing will stop and fail if this method returns None.

        :param parser: The JavaStreamParser in use
        :param reader: The data stream reader
        :param name: The class description name
        :return: An array with the parsed fields or None
        """
        return None
