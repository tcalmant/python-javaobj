#!/usr/bin/env python3
"""
Mimics the core API with the new deserializer
"""

from io import BytesIO
from typing import IO, Iterable

from javaobj.api import ObjectTransformer
from javaobj.core import JavaObjectMarshaller
from javaobj.deserialize.core import JavaStreamParser
from javaobj.transformers import DefaultObjectTransformer

# ------------------------------------------------------------------------------


def load(file_object: IO[bytes], *transformers: ObjectTransformer, **kwargs):
    """
    Deserializes Java primitive data and objects serialized using
    ObjectOutputStream from a file-like object.

    :param file_object: A file-like object
    :param transformers: Custom transformers to use
    :return: The deserialized object
    """
    # Ensure we have the default object transformer
    all_transformers = list(transformers)
    for t in all_transformers:
        if isinstance(t, DefaultObjectTransformer):
            break
    else:
        all_transformers.append(DefaultObjectTransformer())

    # Parse the object(s)
    parser = JavaStreamParser(file_object, all_transformers)
    contents = parser.run()

    if len(contents) == 1:
        # Return the only object as is
        return contents[0]

    # Returns all objects if they are more than one
    return contents


def loads(data: bytes, *transformers: ObjectTransformer, **kwargs):
    """
    Deserializes Java objects and primitive data serialized using
    ObjectOutputStream from bytes.

    :param data: A Java data string
    :param transformers: Custom transformers to use
    :param ignore_remaining_data: If True, don't log an error when unused
                                  trailing bytes are remaining
    :return: The deserialized object
    """
    return load(BytesIO(data), *transformers, **kwargs)


def dumps(obj, *transformers: ObjectTransformer):
    """
    Serializes Java primitive data and objects unmarshaled by load(s) before
    into string.

    :param obj: A Python primitive object, or one loaded using load(s)
    :param transformers: Custom transformers to use
    :return: The serialized data as a string
    """
    marshaller = JavaObjectMarshaller()
    # Add custom transformers
    for transformer in transformers:
        marshaller.add_transformer(transformer)

    return marshaller.dump(obj)
