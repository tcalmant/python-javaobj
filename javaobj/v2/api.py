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

from typing import Optional

from .beans import JavaClassDesc, JavaInstance


class JavaStreamParser:
    pass


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
        raise NotImplementedError
