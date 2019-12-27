#!/usr/bin/env python3
"""
Definition of the object transformer API
"""

from typing import Optional

from .deserialize.beans import JavaClassDesc, JavaInstance


class JavaStreamParser:
    pass


class ObjectTransformer:
    """
    Representation of an object transformer
    """

    def create(
        self,
        classdesc: JavaClassDesc,
        parser: Optional[JavaStreamParser] = None,
    ) -> Optional[JavaInstance]:
        """
        Transforms a parsed Java object into a Python object

        :param classdesc: The description of a Java class
        :return: The Python form of the object, or the original JavaObject
        """
        raise NotImplementedError
