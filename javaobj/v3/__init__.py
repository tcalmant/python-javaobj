#!/usr/bin/env python3
"""
Rewritten version of the un-marshalling and marshalling process of javaobj (v3)

This package targets Python 3.12+ and provides fully typed parsing and
serializing of the Java Object Serialization stream format.

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
from io import BytesIO
from typing import IO, Any

# Javaobj
from ..utils import java_data_fd

# Also expose the beans sub-module so that ``javaobj.v3.beans.JavaInstance``
# works out of the box (same pattern as v2).
from . import beans  # noqa: F401
from .beans import (
    BlockData,
    ClassDataType,
    ClassDescType,
    ExceptionState,
    FieldType,
    JavaArray,
    JavaClass,
    JavaClassDesc,
    JavaEnum,
    JavaField,
    JavaInstance,
    JavaString,
    ParsedContent,
)
from .exceptions import (
    JavaObjError,
    ParseError,
    SecurityError,
    UnexpectedOpcodeError,
    UnsupportedFeatureError,
)
from .parser import JavaStreamParser
from .reader import DataReader
from .transformers import (
    DefaultObjectTransformer,
    NumpyArrayTransformer,
    ObjectTransformer,
)
from .writer import JavaStreamWriter, dump, dumps

__all__ = [
    # Entry points (reading)
    "load",
    "loads",
    # Entry points (writing)
    "dump",
    "dumps",
    "JavaStreamWriter",
    # Transformer API
    "ObjectTransformer",
    "DefaultObjectTransformer",
    "NumpyArrayTransformer",
    # Bean types
    "JavaInstance",
    "JavaArray",
    "JavaString",
    "JavaEnum",
    "JavaClass",
    "JavaClassDesc",
    "JavaField",
    "BlockData",
    "ExceptionState",
    "FieldType",
    "ClassDataType",
    "ClassDescType",
    "ParsedContent",
    # Parser
    "JavaStreamParser",
    "DataReader",
    # Exceptions
    "JavaObjError",
    "ParseError",
    "UnexpectedOpcodeError",
    "UnsupportedFeatureError",
    "SecurityError",
]

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 5, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------------------


def load(
    file_object: IO[bytes],
    *transformers: ObjectTransformer,
    use_numpy_arrays: bool = False,
    max_array_size: int = DataReader.DEFAULT_MAX_ARRAY_SIZE,
    max_depth: int = DataReader.DEFAULT_MAX_DEPTH,
) -> Any:
    """
    Deserializes Java object(s) from a binary file-like object.

    The stream is automatically decompressed if it is GZip-compressed.

    :param file_object: A readable binary stream containing a Java serialized
                        object stream (magic ``0xACED 0x0005``).
    :param transformers: Zero or more custom :class:`ObjectTransformer`
                         instances.  A :class:`DefaultObjectTransformer` is
                         always added unless one is already present.
    :param use_numpy_arrays: When ``True`` and *numpy* is installed, primitive
                             arrays are loaded as ``numpy.ndarray`` objects.
    :param max_array_size: Maximum bytes for a single array allocation.
    :param max_depth: Maximum object-graph recursion depth.
    :return: The parsed object if the stream contains exactly one top-level
             object, or a list of objects if there are several.
             Returns ``None`` for an empty stream.
    :raises ParseError: If the stream is malformed.
    :raises SecurityError: If a safety limit is exceeded.
    :raises UnsupportedFeatureError: If an unsupported protocol feature is
                                     encountered.
    """
    # Auto-decompress GZip streams
    fd = java_data_fd(file_object)

    # Build transformer list, ensuring DefaultObjectTransformer is present
    all_transformers: list[ObjectTransformer] = list(transformers)
    if not any(isinstance(t, DefaultObjectTransformer) for t in all_transformers):
        all_transformers.append(DefaultObjectTransformer())

    if use_numpy_arrays:
        all_transformers.append(NumpyArrayTransformer())

    parser = JavaStreamParser(
        fd,
        all_transformers,
        max_array_size=max_array_size,
        max_depth=max_depth,
    )
    contents = parser.run()

    if not contents:
        return None
    if len(contents) == 1:
        return contents[0]
    return contents


def loads(
    data: bytes,
    *transformers: ObjectTransformer,
    use_numpy_arrays: bool = False,
    max_array_size: int = DataReader.DEFAULT_MAX_ARRAY_SIZE,
    max_depth: int = DataReader.DEFAULT_MAX_DEPTH,
) -> Any:
    """
    Deserializes Java object(s) from a :class:`bytes` object.

    :param data: Raw bytes of a Java serialized stream.
    :param transformers: Optional custom transformers (see :func:`load`).
    :param use_numpy_arrays: See :func:`load`.
    :param max_array_size: See :func:`load`.
    :param max_depth: See :func:`load`.
    :return: Parsed object or list of objects (see :func:`load`).
    """
    return load(
        BytesIO(data),
        *transformers,
        use_numpy_arrays=use_numpy_arrays,
        max_array_size=max_array_size,
        max_depth=max_depth,
    )
