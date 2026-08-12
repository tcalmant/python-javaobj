#!/usr/bin/env python3
"""
Mimics the core API with the new deserializer

:authors: Thomas Calmant
:license: Apache License 2.0
:version: 0.6.1
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

from __future__ import absolute_import

from typing import IO, Any, List  # noqa: F401

try:
    # Python 2
    from StringIO import StringIO as BytesIO
except ImportError:
    # Python 3+
    from io import BytesIO

from ..utils import java_data_fd
from .api import ObjectTransformer  # noqa: F401
from .core import JavaStreamParser
from .transformers import DefaultObjectTransformer, NumpyArrayTransformer

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 6, 1)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------


def _check_transformers(transformers):
    # type: (List[Any]) -> None
    """
    Ensures that the given transformers are instances, not classes.

    Giving a class instead of an instance is a common mistake: the parser
    would then call ``create_instance()`` on the class itself, and the class
    description would be given as the ``self`` argument, which ends in a
    confusing error deep in the parser.

    :param transformers: The transformers given by the caller
    :raise TypeError: A transformer is a class instead of an instance
    """
    for transformer in transformers:
        if isinstance(transformer, type):
            raise TypeError(
                "Transformers must be given as instances, not as classes: "
                "got the class {0}, did you mean {0}() ?".format(
                    transformer.__name__
                )
            )


def load(file_object, *transformers, **kwargs):
    # type: (IO[bytes], ObjectTransformer, Any) -> Any
    """
    Deserializes Java primitive data and objects serialized using
    ObjectOutputStream from a file-like object.

    :param file_object: A file-like object
    :param transformers: Custom transformers to use
    :return: The deserialized object
    :raise TypeError: A transformer class has been given instead of an
                      instance
    """
    # Check file format (uncompress if necessary)
    file_object = java_data_fd(file_object)

    # Ensure we have the default object transformer
    all_transformers = list(transformers)
    _check_transformers(all_transformers)
    for t in all_transformers:
        if isinstance(t, DefaultObjectTransformer):
            break
    else:
        all_transformers.append(DefaultObjectTransformer())

    if kwargs.get("use_numpy_arrays", False):
        # Use the numpy array transformer if requested
        all_transformers.append(NumpyArrayTransformer())

    # Parse the object(s)
    parser = JavaStreamParser(file_object, all_transformers)
    contents = parser.run()

    if len(contents) == 0:
        # Nothing was parsed, but no error
        return None
    elif len(contents) == 1:
        # Return the only object as is
        return contents[0]
    else:
        # Returns all objects if they are more than one
        return contents


def loads(data, *transformers, **kwargs):
    # type: (bytes, ObjectTransformer, Any) -> Any
    """
    Deserializes Java objects and primitive data serialized using
    ObjectOutputStream from bytes.

    :param data: A Java data string
    :param transformers: Custom transformers to use
    :param ignore_remaining_data: If True, don't log an error when unused
                                  trailing bytes are remaining
    :return: The deserialized object
    :raise TypeError: A transformer class has been given instead of an
                      instance
    """
    return load(BytesIO(data), *transformers, **kwargs)
