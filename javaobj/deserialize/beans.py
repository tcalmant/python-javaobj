#!/usr/bin/env python3
"""
Definition of the beans used in javaobj
"""

from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional, Set
import logging

from . import constants
from .stream import DataStreamReader
from ..modifiedutf8 import decode_modified_utf8


class ContentType(IntEnum):
    """
    Types of objects
    """

    INSTANCE = 0
    CLASS = 1
    ARRAY = 2
    STRING = 3
    ENUM = 4
    CLASSDESC = 5
    BLOCKDATA = 6
    EXCEPTIONSTATE = 7


class ClassDescType(IntEnum):
    """
    Types of class descriptions
    """

    NORMALCLASS = 0
    PROXYCLASS = 1


class FieldType(IntEnum):
    """
    Types of class fields
    """

    BYTE = constants.TYPE_BYTE
    CHAR = constants.TYPE_CHAR
    DOUBLE = constants.TYPE_DOUBLE
    FLOAT = constants.TYPE_FLOAT
    INTEGER = constants.TYPE_INTEGER
    LONG = constants.TYPE_LONG
    SHORT = constants.TYPE_SHORT
    BOOLEAN = constants.TYPE_BOOLEAN
    ARRAY = constants.TYPE_ARRAY
    OBJECT = constants.TYPE_OBJECT


class ParsedJavaContent:
    """
    Generic representation of data parsed from the stream
    """

    def __init__(self, content_type: ContentType):
        self.type: ContentType = content_type
        self.is_exception: bool = False
        self.handle: int = 0

    def validate(self) -> None:
        """
        Validity check on the object
        """
        pass


class ExceptionState(ParsedJavaContent):
    """
    Representation of a failed parsing
    """

    def __init__(self, exception_object: ParsedJavaContent, data: bytes):
        super().__init__(ContentType.EXCEPTIONSTATE)
        self.exception_object = exception_object
        self.stream_data = data
        self.handle = exception_object.handle


class ExceptionRead(Exception):
    """
    Exception used to indicate that an exception object has been parsed
    """

    def __init__(self, content: ParsedJavaContent):
        self.exception_object = content


class JavaString(ParsedJavaContent):
    """
    Represents a Java string
    """

    def __init__(self, handle: int, data: bytes):
        super().__init__(ContentType.STRING)
        self.handle = handle
        value, length = decode_modified_utf8(data)
        self.value: str = value
        self.length: int = length

    def __str__(self) -> str:
        return "[String {0:x}: {1}]".format(self.handle, self.value)

    __repr__ = __str__


class JavaField:
    """
    Represents a field in a Java class description
    """

    def __init__(
        self,
        field_type: FieldType,
        name: str,
        class_name: Optional[JavaString] = None,
    ):
        self.type = field_type
        self.name = name
        self.class_name: JavaString = class_name
        self.is_inner_class_reference = False

        if self.class_name:
            self.validate(self.class_name.value)

    def validate(self, java_type: str) -> None:
        """
        Validates the type given as parameter
        """
        if self.type == FieldType.OBJECT:
            if not java_type:
                raise ValueError("Class name can't be empty")

            if java_type[0] != "L" or java_type[-1] != ";":
                raise ValueError(
                    "Invalid object field type: {0}".format(java_type)
                )


class JavaClassDesc(ParsedJavaContent):
    """
    Represents the description of a class
    """

    def __init__(self, class_desc_type: ClassDescType):
        super().__init__(ContentType.CLASSDESC)

        # Type of class description
        self.class_type: ClassDescType = class_desc_type

        # Class name
        self.name: Optional[str] = None

        # Serial version UID
        self.serial_version_uid: int = 0

        # Description flags byte
        self.desc_flags: int = 0

        # Fields in the class
        self.fields: List[JavaField] = []

        # Inner classes
        self.inner_classes: List[JavaClassDesc] = []

        # List of annotations objects
        self.annotations: List[ParsedJavaContent] = []

        # The super class of this one, if any
        self.super_class: JavaClassDesc = None

        # List of the interfaces of the class
        self.interfaces: List[str] = []

        # Set of enum constants
        self.enum_constants: Set[str] = set()

        # Flag to indicate if this is an inner class
        self.is_inner_class: bool = False

        # Flag to indicate if this is a local inner class
        self.is_local_inner_class: bool = False

        # Flag to indicate if this is a static member class
        self.is_static_member_class: bool = False

    def __str__(self):
        return "[classdesc 0x{0:x}: name {1}, uid {2}]".format(
            self.handle, self.name, self.serial_version_uid
        )

    __repr__ = __str__

    def is_array_class(self) -> bool:
        """
        Determines if this is an array type
        """
        return self.name.startswith("[") if self.name else False

    def get_hierarchy(self, classes: List["JavaClassDesc"]) -> None:
        """
        Generates a list of class descriptions in this class's hierarchy, in
        the order described by the Object Stream Serialization Protocol.
        This is the order in which fields are read from the stream.

        :param classes: A list to be filled in with the hierarchy
        """
        if self.super_class is not None:
            if self.super_class.class_type == ClassDescType.PROXYCLASS:
                logging.warning("Hit a proxy class in super class hierarchy")
            else:
                self.super_class.get_hierarchy(classes)

        classes.append(self)

    def validate(self):
        """
        Checks the validity of this class description
        """
        serial_or_extern = (
            constants.SC_SERIALIZABLE | constants.SC_EXTERNALIZABLE
        )
        if (self.desc_flags & serial_or_extern) == 0 and self.fields:
            raise ValueError(
                "Non-serializable, non-externalizable class has fields"
            )

        if self.desc_flags & serial_or_extern == serial_or_extern:
            raise ValueError("Class is both serializable and externalizable")

        if self.desc_flags & constants.SC_ENUM:
            if self.fields or self.interfaces:
                raise ValueError(
                    "Enums shouldn't implement interfaces "
                    "or have non-constant fields"
                )
        else:
            if self.enum_constants:
                raise ValueError(
                    "Non-enum classes shouldn't have enum constants"
                )


class JavaInstance(ParsedJavaContent):
    """
    Represents an instance of Java object
    """

    def __init__(self):
        super().__init__(ContentType.INSTANCE)
        self.classdesc: JavaClassDesc = None
        self.field_data: Dict[JavaClassDesc, Dict[JavaField, Any]] = {}
        self.annotations: Dict[JavaClassDesc, List[ParsedJavaContent]] = {}

    def __str__(self):
        return "[instance 0x{0:x}: type {1}]".format(
            self.handle, self.classdesc.name
        )

    __repr__ = __str__

    def load_from_blockdata(
        self, reader: DataStreamReader, indent: int = 0
    ) -> bool:
        """
        Reads content stored in a block data
        """
        return False

    def load_from_instance(
        self, instance: "JavaInstance", indent: int = 0
    ) -> bool:
        """
        Load content from a parsed instance object
        """
        return False


class JavaClass(ParsedJavaContent):
    """
    Represents a stored Java class
    """

    def __init__(self, handle: int, class_desc: JavaClassDesc):
        super().__init__(ContentType.CLASS)
        self.handle = handle
        self.classdesc = class_desc

    def __str__(self):
        return "[class 0x{0:x}: {1}]".format(self.handle, self.classdesc)

    __repr__ = __str__


class JavaEnum(ParsedJavaContent):
    """
    Represents an enumeration value
    """

    def __init__(
        self, handle: int, class_desc: JavaClassDesc, value: JavaString
    ):
        super().__init__(ContentType.ENUM)
        self.handle = handle
        self.class_desc = class_desc
        self.value = value

    def __str__(self):
        return "[Enum 0x{0:x}: {1}]".format(self.handle, self.value)

    __repr__ = __str__


class JavaArray(ParsedJavaContent):
    """
    Represents a Java array
    """

    def __init__(
        self,
        handle: int,
        class_desc: JavaClassDesc,
        field_type: FieldType,
        content: List[Any],
    ):
        super().__init__(ContentType.ARRAY)
        self.handle = handle
        self.class_desc = class_desc
        self.field_type = field_type
        self.content = content

    def __str__(self):
        return "[array 0x{0:x}: {1} items]".format(
            self.handle, len(self.content)
        )

    __repr__ = __str__


class BlockData(ParsedJavaContent):
    """
    Represents a data block
    """

    def __init__(self, data: bytes):
        super().__init__(ContentType.BLOCKDATA)
        self.data = data

    def __str__(self):
        return "[blockdata 0x{0:x}: {1} bytes]".format(
            self.handle, len(self.data)
        )

    __repr__ = __str__
