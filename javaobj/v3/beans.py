#!/usr/bin/env python3
"""
Definition of the beans used to represent the parsed objects (v3)

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
import warnings
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

# Javaobj
from ..constants import ClassDescFlags, TypeCode

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 5, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------

__all__ = [
    "FieldType",
    "ClassDescType",
    "ClassDataType",
    "JavaField",
    "JavaClassDesc",
    "JavaInstance",
    "JavaArray",
    "JavaString",
    "JavaEnum",
    "JavaClass",
    "BlockData",
    "ExceptionState",
    "ParsedContent",
]


# ------------------------------------------------------------------------------
# Enumerations
# ------------------------------------------------------------------------------


class FieldType(IntEnum):
    """
    Java type codes as used in class-descriptor field entries.

    Values match the single-character ASCII type codes defined by the
    Java Object Serialization Protocol (e.g. ``B`` → byte, ``I`` → int …).
    """

    BYTE = TypeCode.TYPE_BYTE.value  # 'B' – signed byte
    CHAR = TypeCode.TYPE_CHAR.value  # 'C' – UTF-16 code unit (2 bytes)
    DOUBLE = TypeCode.TYPE_DOUBLE.value  # 'D' – IEEE-754 double
    FLOAT = TypeCode.TYPE_FLOAT.value  # 'F' – IEEE-754 float
    INTEGER = TypeCode.TYPE_INTEGER.value  # 'I' – 32-bit signed int
    LONG = TypeCode.TYPE_LONG.value  # 'J' – 64-bit signed long
    SHORT = TypeCode.TYPE_SHORT.value  # 'S' – 16-bit signed short
    BOOLEAN = TypeCode.TYPE_BOOLEAN.value  # 'Z' – boolean
    ARRAY = TypeCode.TYPE_ARRAY.value  # '[' – array reference
    OBJECT = TypeCode.TYPE_OBJECT.value  # 'L' – object reference


class ClassDescType(IntEnum):
    """Whether a class descriptor represents a normal class or a proxy."""

    NORMALCLASS = 0
    PROXYCLASS = 1


class ClassDataType(IntEnum):
    """
    How an instance's data is laid out in the stream.

    Derived from the ``desc_flags`` byte of its :class:`JavaClassDesc`.
    """

    NOWRCLASS = 0  # SC_SERIALIZABLE, no writeObject
    WRCLASS = 1  # SC_SERIALIZABLE + SC_WRITE_METHOD
    EXTERNAL_CONTENTS = 2  # SC_EXTERNALIZABLE, no SC_BLOCK_DATA
    OBJECT_ANNOTATION = 3  # SC_EXTERNALIZABLE + SC_BLOCK_DATA


# ------------------------------------------------------------------------------
# Field descriptor
# ------------------------------------------------------------------------------


@dataclass(slots=True, eq=False)
class JavaField:
    """
    A single field entry in a :class:`JavaClassDesc`.

    Equality and hashing use **object identity** (like plain Python classes)
    so that ``JavaField`` instances can be used as dict keys and compared
    across the same parsing session.
    """

    type: FieldType
    name: str
    # For OBJECT / ARRAY fields this holds the binary class name
    # (e.g. ``Ljava/lang/String;`` or ``[B``).
    class_name: str | None = None


# ------------------------------------------------------------------------------
# Class descriptor
# ------------------------------------------------------------------------------


@dataclass(slots=True, eq=False)
class JavaClassDesc:
    """
    Full description of a Java class as parsed from a TC_CLASSDESC or
    TC_PROXYCLASSDESC record.

    Equality and hashing use **object identity** so that ``JavaClassDesc``
    instances can be used as dict keys when building ``field_data`` and
    ``annotations`` maps.
    """

    handle: int
    name: str
    serial_version_uid: int
    desc_flags: int
    class_type: ClassDescType = ClassDescType.NORMALCLASS
    fields: list[JavaField] = field(default_factory=list)
    super_class: "JavaClassDesc | None" = None
    # Interface names (only for proxy classes)
    interfaces: list[str] = field(default_factory=list)
    # Class annotations (blockdata / objects written by annotateClass)
    annotations: list[Any] = field(default_factory=list)
    # Enum constant names observed in this stream
    enum_constants: set[str] = field(default_factory=set)
    # True when this descriptor is a super-class of another descriptor
    is_super_class: bool = False

    # ------------------------------------------------------------------
    # v1 / v2 compatibility aliases
    # ------------------------------------------------------------------

    @property
    def serialVersionUID(self) -> int:
        """Alias for ``serial_version_uid`` (v1/v2 API compatibility)."""
        return self.serial_version_uid

    @property
    def flags(self) -> int:
        """Alias for ``desc_flags`` (v1/v2 API compatibility)."""
        return self.desc_flags

    @property
    def fields_names(self) -> list[str]:
        """Returns the ordered list of field names."""
        return [f.name for f in self.fields]

    @property
    def fields_types(self) -> list[FieldType]:
        """Returns the ordered list of field types."""
        return [f.type for f in self.fields]

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def data_type(self) -> ClassDataType:
        """
        Derives the :class:`ClassDataType` from the descriptor flags.

        :raises ValueError: If the flags combination is unsupported.
        """
        if ClassDescFlags.SC_SERIALIZABLE & self.desc_flags:
            return (
                ClassDataType.WRCLASS
                if (ClassDescFlags.SC_WRITE_METHOD & self.desc_flags)
                else ClassDataType.NOWRCLASS
            )
        if ClassDescFlags.SC_EXTERNALIZABLE & self.desc_flags:
            return (
                ClassDataType.OBJECT_ANNOTATION
                if (ClassDescFlags.SC_BLOCK_DATA & self.desc_flags)
                else ClassDataType.EXTERNAL_CONTENTS
            )
        raise ValueError(f"Cannot derive data type from desc_flags 0x{self.desc_flags:02x}")

    def get_hierarchy(self) -> "list[JavaClassDesc]":
        """
        Returns the class hierarchy from the topmost ancestor to ``self``,
        in the order used by the Java serialization protocol.
        """
        classes: list[JavaClassDesc] = []
        if self.super_class is not None:
            classes.extend(self.super_class.get_hierarchy())
        classes.append(self)
        return classes

    def validate(self) -> None:
        """
        Checks that the descriptor is internally consistent.

        :raises ValueError: If the descriptor is malformed.
        """
        serial_or_extern = ClassDescFlags.SC_SERIALIZABLE | ClassDescFlags.SC_EXTERNALIZABLE
        if (self.desc_flags & serial_or_extern) == 0 and self.fields:
            raise ValueError("Non-serializable, non-externalizable class has fields")
        if (self.desc_flags & serial_or_extern) == serial_or_extern:
            raise ValueError("Class is both serializable and externalizable")
        if self.desc_flags & ClassDescFlags.SC_ENUM:
            if self.fields or self.interfaces:
                raise ValueError("Enum class must not have non-constant fields or interfaces")
        else:
            if self.enum_constants:
                raise ValueError("Non-enum class must not have enum constants")

    def __str__(self) -> str:
        return f"[classdesc 0x{self.handle:x}: name={self.name!r}, uid={self.serial_version_uid}]"

    __repr__ = __str__


# ------------------------------------------------------------------------------
# Instance
# ------------------------------------------------------------------------------


@dataclass
class JavaInstance:
    """
    A deserialized Java object instance (TC_OBJECT).

    ``field_data`` maps each :class:`JavaClassDesc` in the class hierarchy to
    a ``{JavaField: value}`` dict.  ``annotations`` maps each class descriptor
    to the list of :data:`ParsedContent` items written by ``writeObject``.

    .. note::
        This class intentionally does **not** use ``slots=True`` so that
        transformer subclasses can use multiple inheritance with built-in
        types such as :class:`list`, :class:`dict`, or :class:`set`.
        All fields have defaults so that ``JavaInstance()`` can be called
        with no arguments during construction (the parser sets them after).
    """

    handle: int = 0
    classdesc: JavaClassDesc | None = None  # set by the parser after creation
    field_data: dict[JavaClassDesc, dict[JavaField, Any]] = field(default_factory=dict)
    annotations: dict[JavaClassDesc, list[Any]] = field(default_factory=dict)
    is_exception: bool = False

    # ------------------------------------------------------------------
    # Field access helpers
    # ------------------------------------------------------------------

    def get_field(
        self,
        name: str,
        class_desc: JavaClassDesc | None = None,
    ) -> Any:
        """
        Returns the value of a field by name.

        If *class_desc* is provided the search is restricted to that class,
        which avoids the ambiguity that can arise when two classes in the
        hierarchy declare a field with the same name.

        :raises AttributeError: If the field is not found.
        """
        search = {class_desc: self.field_data[class_desc]} if class_desc is not None else self.field_data
        for cd_fields in search.values():
            for f, v in cd_fields.items():
                if f.name == name:
                    return v
        raise AttributeError(name)

    def __getattr__(self, name: str) -> Any:
        """
        Flat attribute access to instance fields (v1/v2 API compatibility).

        When multiple classes in the hierarchy define a field with the same
        name, a :class:`UserWarning` is emitted and the first match is
        returned.  Use :meth:`get_field` with an explicit *class_desc* to
        resolve ambiguity.
        """
        # Note: __getattr__ is only called when normal attribute lookup fails,
        # so there is no risk of infinite recursion here.
        matches: list[Any] = [
            v for cd_fields in self.field_data.values() for f, v in cd_fields.items() if f.name == name
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            warnings.warn(
                f"Ambiguous field '{name}': found in {len(matches)} classes "
                "in the hierarchy. Use get_field(name, class_desc) for "
                "unambiguous access.",
                stacklevel=2,
            )
            return matches[0]
        raise AttributeError(name)

    def get_class(self) -> JavaClassDesc | None:
        """Returns the class descriptor of this instance."""
        return self.classdesc

    def load_from_instance(self) -> bool:
        """
        Post-processing hook called after parsing.

        Transformer subclasses can override this to convert parsed field data
        into a more convenient Python representation.

        :return: ``True`` if post-processing succeeded, ``False`` otherwise.
        """
        return False

    def load_from_blockdata(self, parser: Any, reader: Any) -> bool:
        """
        Hook for ``SC_EXTERNALIZABLE + SC_BLOCK_DATA`` classes.

        Transformer subclasses should override this to decode the raw block
        data written by the Java ``writeExternal`` method.

        :return: ``True`` if decoding succeeded, ``False`` otherwise.
        """
        return False

    def __str__(self) -> str:
        name = self.classdesc.name if self.classdesc else "<no class>"
        return f"[instance 0x{self.handle:x}: type={name!r}]"

    __repr__ = __str__


# ------------------------------------------------------------------------------
# Array
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class JavaArray:
    """
    A deserialized Java array (TC_ARRAY).

    For ``TYPE_BYTE`` arrays ``data`` holds a :class:`bytes` object.
    For all other element types ``data`` is a :class:`list`.
    """

    handle: int
    classdesc: JavaClassDesc
    element_type: FieldType
    data: bytes | list[Any]

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, idx: int) -> Any:
        return self.data[idx]  # type: ignore[index]

    def __str__(self) -> str:
        return f"[array 0x{self.handle:x}: type={self.element_type.name}, len={len(self.data)}]"

    __repr__ = __str__


# ------------------------------------------------------------------------------
# String
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class JavaString:
    """A Java string decoded from TC_STRING or TC_LONGSTRING."""

    handle: int
    value: str

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return repr(self.value)

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, JavaString):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented


# ------------------------------------------------------------------------------
# Enum
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class JavaEnum:
    """A Java enum constant (TC_ENUM)."""

    handle: int
    classdesc: JavaClassDesc
    constant: JavaString

    @property
    def name(self) -> str:
        """The binary class name of the enum type."""
        return self.classdesc.name

    def __str__(self) -> str:
        return f"[enum {self.classdesc.name}.{self.constant.value}]"

    __repr__ = __str__

    def __hash__(self) -> int:
        return hash((self.classdesc.name, self.constant.value))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, JavaEnum):
            return self.classdesc.name == other.classdesc.name and self.constant.value == other.constant.value
        return NotImplemented


# ------------------------------------------------------------------------------
# Class reference
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class JavaClass:
    """Represents a ``java.lang.Class`` token (TC_CLASS)."""

    handle: int
    classdesc: JavaClassDesc

    @property
    def name(self) -> str:
        """The binary name of the represented class."""
        return self.classdesc.name

    def __str__(self) -> str:
        return f"[class {self.classdesc.name!r}]"

    __repr__ = __str__


# ------------------------------------------------------------------------------
# Block data
# ------------------------------------------------------------------------------


@dataclass(slots=True, eq=False)
class BlockData:
    """Raw bytes from a TC_BLOCKDATA / TC_BLOCKDATALONG record."""

    data: bytes
    handle: int = 0

    def __eq__(self, other: object) -> bool:
        """
        Compares block data with other ``BlockData`` instances or with
        ``bytes`` / ``str`` directly (v1/v2 API compatibility).
        """
        if isinstance(other, BlockData):
            return self.data == other.data
        if isinstance(other, (bytes, bytearray)):
            return self.data == bytes(other)
        if isinstance(other, str):
            return self.data == other.encode("latin-1")
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.data)

    def __str__(self) -> str:
        return f"[blockdata len={len(self.data)}]"

    __repr__ = __str__


# ------------------------------------------------------------------------------
# Exception state
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class ExceptionState:
    """
    Wrapper produced when a TC_EXCEPTION record is encountered.

    The ``exception_object`` holds the parsed Java exception instance and
    ``stream_data`` preserves the raw bytes for diagnostic purposes.
    """

    exception_object: JavaInstance
    stream_data: bytes
    handle: int = 0
    is_exception: bool = True

    def __str__(self) -> str:
        return f"[ExceptionState 0x{self.handle:x}]"

    __repr__ = __str__


# ------------------------------------------------------------------------------
# Union type alias
# ------------------------------------------------------------------------------

type ParsedContent = (
    JavaInstance
    | JavaArray
    | JavaString
    | JavaEnum
    | JavaClass
    | JavaClassDesc
    | BlockData
    | ExceptionState
    | None
)
