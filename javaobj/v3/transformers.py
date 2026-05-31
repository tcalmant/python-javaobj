#!/usr/bin/env python3
"""
Defines the object transformers for javaobj v3

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
import functools
import struct
from typing import TYPE_CHECKING, Any

# Numpy (optional)
try:
    import numpy  # type: ignore[import-untyped]
except ImportError:
    numpy = None  # type: ignore[assignment]

# Javaobj
from ..constants import TerminalCode, TypeCode
from .beans import BlockData, JavaClassDesc, JavaInstance
from .reader import DataReader

if TYPE_CHECKING:
    from .parser import JavaStreamParser

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 5, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------

__all__ = [
    "ObjectTransformer",
    "DefaultObjectTransformer",
    "NumpyArrayTransformer",
]


# ------------------------------------------------------------------------------
# Base transformer interface
# ------------------------------------------------------------------------------


class ObjectTransformer:
    """
    Base class for v3 object transformers.

    Override any combination of the three hook methods to customise how
    specific Java classes are represented in Python.  Returning ``None``
    from any method signals that this transformer does not handle the case
    and the next transformer (or the default behaviour) should be tried.
    """

    def create_instance(self, classdesc: JavaClassDesc) -> JavaInstance | None:
        """
        Returns a custom :class:`~javaobj.v3.beans.JavaInstance` subclass
        for the given class descriptor, or ``None`` to use the default
        :class:`~javaobj.v3.beans.JavaInstance`.

        The parser will set ``.handle``, ``.classdesc``, ``.field_data``
        and ``.annotations`` on the returned object after this call.
        """
        return None

    def load_array(
        self,
        reader: DataReader,
        type_code: TypeCode,
        size: int,
    ) -> bytes | list[Any] | None:
        """
        Reads and returns the content of a Java array of *size* elements.

        Returns ``None`` to fall back to the default element-by-element
        reading logic.
        """
        return None

    def load_custom_writeObject(
        self,
        parser: "JavaStreamParser",
        reader: DataReader,
        class_name: str,
    ) -> Any | None:
        """
        Handles the content of a class that uses a custom ``writeObject``
        / ``readExternal`` method unknown to the default transformers.

        Returns ``None`` to indicate that this transformer cannot handle
        the class.
        """
        return None


# ------------------------------------------------------------------------------
# Collection / primitive transformer classes
# ------------------------------------------------------------------------------


class JavaList(list, JavaInstance):
    """Python list backed by a Java ArrayList or LinkedList."""

    HANDLED_CLASSES: tuple[str, ...] = (
        "java.util.ArrayList",
        "java.util.LinkedList",
    )

    def __init__(self) -> None:
        list.__init__(self)
        JavaInstance.__init__(self)

    def load_from_instance(self) -> bool:
        for cd, ann_list in self.annotations.items():
            if cd.name in self.HANDLED_CLASSES:
                # The first annotation entry is the capacity int; skip it.
                self.extend(a for a in ann_list[1:])
                return True
        return False


@functools.total_ordering
class JavaPrimitiveClass(JavaInstance):
    """
    Base for Java wrapper classes that box a single primitive value
    (Boolean, Integer, Long …).
    """

    HANDLED_CLASSES: str | tuple[str, ...] = ()

    def __init__(self) -> None:
        JavaInstance.__init__(self)
        self.value: Any = None

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return repr(self.value)

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        return self.value == other  # type: ignore[no-any-return]

    def __lt__(self, other: object) -> bool:
        return self.value < other  # type: ignore[operator]

    def load_from_instance(self) -> bool:
        for fields in self.field_data.values():
            for f, v in fields.items():
                if f.name == "value":
                    self.value = v
                    return True
        return False


class JavaBool(JavaPrimitiveClass):
    """Represents a Java ``Boolean`` wrapper object."""

    HANDLED_CLASSES = "java.lang.Boolean"

    def __bool__(self) -> bool:
        return bool(self.value)


class JavaInt(JavaPrimitiveClass):
    """Represents a Java ``Integer`` or ``Long`` wrapper object."""

    HANDLED_CLASSES = ("java.lang.Integer", "java.lang.Long")

    def __int__(self) -> int:
        return int(self.value)


class JavaMap(dict, JavaInstance):
    """Python dict backed by a Java HashMap or TreeMap."""

    HANDLED_CLASSES: tuple[str, ...] = (
        "java.util.HashMap",
        "java.util.TreeMap",
    )

    def __init__(self) -> None:
        dict.__init__(self)
        JavaInstance.__init__(self)

    def load_from_instance(self) -> bool:
        for cd, ann_list in self.annotations.items():
            if cd.name in self.HANDLED_CLASSES:
                # Annotation[0] is load-factor/capacity; skip it.
                it = iter(ann_list[1:])
                for key, value in zip(it, it):
                    self[key] = value
                return True
        return False


class JavaLinkedHashMap(JavaMap):
    """Java LinkedHashMap with custom block-data serialization."""

    HANDLED_CLASSES = ("java.util.LinkedHashMap",)

    def load_from_blockdata(self, parser: "JavaStreamParser", reader: DataReader) -> bool:
        # Read HashMap capacity / load-factor fields
        self.buckets: int = reader.read_int()
        self.size: int = reader.read_int()

        for _ in range(self.size):
            key_opcode = reader.read_byte()
            key = parser._read_content(key_opcode, block_data_allowed=True)

            val_opcode = reader.read_byte()
            value = parser._read_content(val_opcode, block_data_allowed=True)
            self[key] = value

        end_code = reader.read_byte()
        if end_code != TerminalCode.TC_ENDBLOCKDATA:
            raise ValueError(f"Expected TC_ENDBLOCKDATA, got 0x{end_code:02x}")
        final_byte = reader.read_byte()
        if final_byte != 0:
            raise ValueError(f"Expected trailing 0x00, got 0x{final_byte:02x}")
        return True


class JavaSet(set, JavaInstance):
    """Python set backed by a Java HashSet or LinkedHashSet."""

    HANDLED_CLASSES: tuple[str, ...] = (
        "java.util.HashSet",
        "java.util.LinkedHashSet",
    )

    def __init__(self) -> None:
        set.__init__(self)
        JavaInstance.__init__(self)

    def load_from_instance(self) -> bool:
        for cd, ann_list in self.annotations.items():
            if cd.name in self.HANDLED_CLASSES:
                # ann_list[0] is load-factor/capacity; skip it.
                self.update(a for a in ann_list[1:])
                return True
        return False


class JavaTreeSet(JavaSet):
    """Python set backed by a Java TreeSet."""

    HANDLED_CLASSES = ("java.util.TreeSet",)

    def load_from_instance(self) -> bool:
        for cd, ann_list in self.annotations.items():
            if cd.name in self.HANDLED_CLASSES:
                # ann_list[0] is comparator, ann_list[1] is size; skip both.
                self.update(a for a in ann_list[2:])
                return True
        return False


def _read_struct_from_bytes(data: bytes, fmt: str) -> tuple[tuple[Any, ...], bytes]:
    """Helper: unpacks *fmt* from the start of *data* and returns remaining."""
    size = struct.calcsize(fmt)
    values = struct.unpack(fmt, data[:size])
    return values, data[size:]


class JavaTime(JavaInstance):
    """
    Represents instances of the ``java.time`` package serialised via the
    ``java.time.Ser`` proxy class.
    """

    HANDLED_CLASSES = ("java.time.Ser",)

    DURATION_TYPE = 1
    INSTANT_TYPE = 2
    LOCAL_DATE_TYPE = 3
    LOCAL_TIME_TYPE = 4
    LOCAL_DATE_TIME_TYPE = 5
    ZONE_DATE_TIME_TYPE = 6
    ZONE_REGION_TYPE = 7
    ZONE_OFFSET_TYPE = 8
    OFFSET_TIME_TYPE = 9
    OFFSET_DATE_TIME_TYPE = 10
    YEAR_TYPE = 11
    YEAR_MONTH_TYPE = 12
    MONTH_DAY_TYPE = 13
    PERIOD_TYPE = 14

    def __init__(self) -> None:
        JavaInstance.__init__(self)
        self.type: int = -1
        self.year: int | None = None
        self.month: int | None = None
        self.day: int | None = None
        self.hour: int | None = None
        self.minute: int | None = None
        self.second: int | None = None
        self.nano: int | None = None
        self.offset: int | None = None
        self.zone: str | None = None

    def __str__(self) -> str:
        return (
            f"JavaTime(type=0x{self.type:x}, "
            f"year={self.year}, month={self.month}, day={self.day}, "
            f"hour={self.hour}, minute={self.minute}, second={self.second}, "
            f"nano={self.nano}, offset={self.offset}, zone={self.zone})"
        )

    def load_from_blockdata(self, parser: "JavaStreamParser", reader: DataReader) -> bool:
        # Block data is handled entirely inside load_from_instance via
        # the annotations.  Accept the call and let load_from_instance do
        # the real work.
        return True

    def load_from_instance(self) -> bool:
        for cd, ann_list in self.annotations.items():
            if cd.name not in self.HANDLED_CLASSES:
                continue
            if not ann_list or not isinstance(ann_list[0], BlockData):
                return False

            # The raw bytes are stored in the BlockData annotation.
            content: bytes = ann_list[0].data
            (self.type,), content = _read_struct_from_bytes(content, ">b")

            handlers = {
                self.DURATION_TYPE: self._do_duration,
                self.INSTANT_TYPE: self._do_instant,
                self.LOCAL_DATE_TYPE: self._do_local_date,
                self.LOCAL_DATE_TIME_TYPE: self._do_local_date_time,
                self.LOCAL_TIME_TYPE: self._do_local_time,
                self.ZONE_DATE_TIME_TYPE: self._do_zoned_date_time,
                self.ZONE_OFFSET_TYPE: self._do_zone_offset,
                self.ZONE_REGION_TYPE: self._do_zone_region,
                self.OFFSET_TIME_TYPE: self._do_offset_time,
                self.OFFSET_DATE_TIME_TYPE: self._do_offset_date_time,
                self.YEAR_TYPE: self._do_year,
                self.YEAR_MONTH_TYPE: self._do_year_month,
                self.MONTH_DAY_TYPE: self._do_month_day,
                self.PERIOD_TYPE: self._do_period,
            }
            handler = handlers.get(self.type)
            if handler is not None:
                handler(content)
            return True
        return False

    # ------------------------------------------------------------------
    # Internal time-type handlers
    # ------------------------------------------------------------------

    def _do_duration(self, data: bytes) -> bytes:
        (self.second, self.nano), data = _read_struct_from_bytes(data, ">qi")
        return data

    def _do_instant(self, data: bytes) -> bytes:
        (self.second, self.nano), data = _read_struct_from_bytes(data, ">qi")
        return data

    def _do_local_date(self, data: bytes) -> bytes:
        (self.year, self.month, self.day), data = _read_struct_from_bytes(data, ">ibb")
        return data

    def _do_local_time(self, data: bytes) -> bytes:
        (hour,), data = _read_struct_from_bytes(data, ">b")
        minute = second = nano = 0

        if hour < 0:
            hour = ~hour
        else:
            (minute,), data = _read_struct_from_bytes(data, ">b")
            if minute < 0:
                minute = ~minute
            else:
                (second,), data = _read_struct_from_bytes(data, ">b")
                if second < 0:
                    second = ~second
                else:
                    (nano,), data = _read_struct_from_bytes(data, ">i")

        self.hour, self.minute, self.second, self.nano = (
            hour,
            minute,
            second,
            nano,
        )
        return data

    def _do_local_date_time(self, data: bytes) -> bytes:
        data = self._do_local_date(data)
        data = self._do_local_time(data)
        return data

    def _do_zoned_date_time(self, data: bytes) -> bytes:
        data = self._do_local_date_time(data)
        data = self._do_zone_offset(data)
        data = self._do_zone_region(data)
        return data

    def _do_zone_offset(self, data: bytes) -> bytes:
        (offset_byte,), data = _read_struct_from_bytes(data, ">b")
        if offset_byte == 127:
            (self.offset,), data = _read_struct_from_bytes(data, ">i")
        else:
            self.offset = offset_byte * 900
        return data

    def _do_zone_region(self, data: bytes) -> bytes:
        # 2-byte length + UTF-8 string (standard UTF-8, not modified)
        (length,), data = _read_struct_from_bytes(data, ">H")
        self.zone = data[:length].decode("utf-8")
        return data[length:]

    def _do_offset_time(self, data: bytes) -> bytes:
        data = self._do_local_time(data)
        data = self._do_zone_offset(data)
        return data

    def _do_offset_date_time(self, data: bytes) -> bytes:
        data = self._do_local_date_time(data)
        data = self._do_zone_offset(data)
        return data

    def _do_year(self, data: bytes) -> bytes:
        (self.year,), data = _read_struct_from_bytes(data, ">i")
        return data

    def _do_year_month(self, data: bytes) -> bytes:
        (self.year, self.month), data = _read_struct_from_bytes(data, ">ib")
        return data

    def _do_month_day(self, data: bytes) -> bytes:
        (self.month, self.day), data = _read_struct_from_bytes(data, ">bb")
        return data

    def _do_period(self, data: bytes) -> bytes:
        (self.year, self.month, self.day), data = _read_struct_from_bytes(data, ">iii")
        return data


# ------------------------------------------------------------------------------
# DefaultObjectTransformer
# ------------------------------------------------------------------------------


class DefaultObjectTransformer(ObjectTransformer):
    """
    Built-in transformer that covers the most common Java standard-library
    classes.

    Handled classes
    ~~~~~~~~~~~~~~~
    * ``java.lang.Boolean``, ``java.lang.Integer``, ``java.lang.Long``
    * ``java.util.ArrayList``, ``java.util.LinkedList``
    * ``java.util.HashMap``, ``java.util.TreeMap``, ``java.util.LinkedHashMap``
    * ``java.util.HashSet``, ``java.util.LinkedHashSet``, ``java.util.TreeSet``
    * ``java.time.Ser``
    """

    _KNOWN_TRANSFORMERS: tuple[type[JavaInstance], ...] = (
        JavaBool,
        JavaInt,
        JavaList,
        JavaMap,
        JavaLinkedHashMap,
        JavaSet,
        JavaTreeSet,
        JavaTime,
    )

    def __init__(self) -> None:
        self._type_mapper: dict[str, type[JavaInstance]] = {}
        for klass in self._KNOWN_TRANSFORMERS:
            handled = klass.HANDLED_CLASSES  # type: ignore[attr-defined]
            if isinstance(handled, str):
                self._type_mapper[handled] = klass
            else:
                for name in handled:
                    self._type_mapper[name] = klass

    def create_instance(self, classdesc: JavaClassDesc) -> JavaInstance | None:
        """
        Returns a specialised :class:`JavaInstance` subclass for known Java
        types, or ``None`` for unknown types.
        """
        mapped = self._type_mapper.get(classdesc.name)
        if mapped is None:
            return None
        instance = mapped()
        instance.classdesc = classdesc
        return instance

    def handles(self, class_name: str) -> bool:
        """Returns ``True`` if this transformer knows how to handle *class_name*."""
        return class_name in self._type_mapper


# ------------------------------------------------------------------------------
# NumpyArrayTransformer
# ------------------------------------------------------------------------------


class NumpyArrayTransformer(ObjectTransformer):
    """
    Loads primitive Java arrays as NumPy arrays when *numpy* is available.

    NumPy dtype mapping (corrected from v1/v2):
        * ``TYPE_CHAR`` → ``>u2`` (2-byte unsigned, UTF-16; **not** ``b``)
        * ``TYPE_BYTE`` → ``B``  (unsigned byte)
        * All other types use their natural NumPy big-endian counterparts.
    """

    NUMPY_TYPE_MAP: dict[TypeCode, str] = {
        TypeCode.TYPE_BYTE: "B",
        TypeCode.TYPE_CHAR: ">u2",  # Fixed: Java char = 2-byte unsigned
        TypeCode.TYPE_DOUBLE: ">d",
        TypeCode.TYPE_FLOAT: ">f",
        TypeCode.TYPE_INTEGER: ">i",
        TypeCode.TYPE_LONG: ">q",
        TypeCode.TYPE_SHORT: ">h",
        TypeCode.TYPE_BOOLEAN: ">B",
    }

    def load_array(
        self,
        reader: DataReader,
        type_code: TypeCode,
        size: int,
    ) -> Any | None:
        """
        Reads *size* elements from the stream as a NumPy array.

        Returns ``None`` if NumPy is not installed or the element type has
        no NumPy mapping.
        """
        if numpy is None:
            return None
        dtype = self.NUMPY_TYPE_MAP.get(type_code)
        if dtype is None:
            return None
        return numpy.fromfile(reader._fd, dtype=dtype, count=size)
