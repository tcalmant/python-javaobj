#!/usr/bin/env python3
"""
Serializer for the Java Object Serialization stream format (v3)

Produces a byte stream readable by Java's ``ObjectInputStream`` from v3 bean
objects (:class:`~javaobj.v3.beans.JavaInstance`, :class:`~javaobj.v3.beans.JavaArray`,
etc.).

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
import logging
import struct
from io import BytesIO
from typing import IO, Any

# Javaobj
from ..constants import StreamConstants, TerminalCode
from .beans import (
    BlockData,
    ClassDataType,
    ClassDescType,
    FieldType,
    JavaArray,
    JavaClass,
    JavaClassDesc,
    JavaEnum,
    JavaInstance,
    JavaString,
    ParsedContent,
)
from .exceptions import UnsupportedFeatureError

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 5, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------

__all__ = ["JavaStreamWriter", "dump", "dumps"]

_log = logging.getLogger("javaobj.v3.writer")

# ------------------------------------------------------------------------------
# Modified UTF-8 encoder
# ------------------------------------------------------------------------------


def _encode_mutf8(string: str) -> bytes:
    """
    Encodes a Unicode string to Java Modified UTF-8 bytes.

    Differences from standard UTF-8:

    * The null character (U+0000) is encoded as two bytes ``\\xC0\\x80``
      instead of a single zero byte.
    * Supplementary characters (U+10000–U+10FFFF) are encoded as two
      three-byte surrogate-pair sequences (six bytes total) instead of the
      standard four-byte encoding.
    """
    out = bytearray()
    for char in string:
        cp = ord(char)
        if cp == 0x0000:
            # Modified UTF-8: null → 0xC0 0x80
            out += b"\xc0\x80"
        elif cp <= 0x007F:
            out.append(cp)
        elif cp <= 0x07FF:
            out += bytes([0xC0 | (cp >> 6), 0x80 | (cp & 0x3F)])
        elif cp <= 0xFFFF:
            out += bytes(
                [
                    0xE0 | (cp >> 12),
                    0x80 | ((cp >> 6) & 0x3F),
                    0x80 | (cp & 0x3F),
                ]
            )
        else:
            # Supplementary character: encode as surrogate pair, each as a
            # 3-byte modified-UTF-8 sequence (6 bytes total).
            cp -= 0x10000
            high = 0xD800 | (cp >> 10)
            low = 0xDC00 | (cp & 0x3FF)
            out += bytes(
                [
                    0xED,
                    0xA0 | ((high >> 6) & 0x0F),
                    0x80 | (high & 0x3F),
                    0xED,
                    0xB0 | ((low >> 6) & 0x0F),
                    0x80 | (low & 0x3F),
                ]
            )
    return bytes(out)


# ------------------------------------------------------------------------------
# Writer
# ------------------------------------------------------------------------------


class JavaStreamWriter:
    """
    Serializes v3 bean objects to the Java Object Serialization stream format.

    The generated stream is fully compatible with Java's ``ObjectInputStream``.

    Usage::

        with open("out.ser", "wb") as fd:
            writer = JavaStreamWriter(fd)
            writer.write_stream(my_instance)

    Or using the module-level helpers::

        data = javaobj.v3.dumps(my_instance)
        javaobj.v3.dump(fd, my_instance)
    """

    def __init__(self, fd: IO[bytes]) -> None:
        self._fd = fd
        # Maps id(obj) → allocated handle (int, starting at BASE_REFERENCE_IDX)
        self._handle_map: dict[int, int] = {}
        self._next_handle: int = int(StreamConstants.BASE_REFERENCE_IDX)
        # Cached JavaString wrappers for class-name strings found inside
        # JavaField descriptors.  Keyed by the string value so that identical
        # class names (e.g. "Ljava/lang/String;") are written only once and
        # referenced thereafter.
        self._classname_strings: dict[str, JavaString] = {}

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def write_stream(self, *objects: ParsedContent) -> None:
        """
        Writes the Java serialization magic header followed by one or more
        top-level content objects.

        Call this exactly once to produce a complete, self-contained stream.

        :param objects: Top-level objects to write.  Pass several to create
                        a stream that requires multiple ``readObject()`` calls
                        on the Java side.
        :raises UnsupportedFeatureError: If an object type cannot be
                                         serialized (e.g. externalizable
                                         Protocol-v1 classes).
        """
        self._write_header()
        for obj in objects:
            self._write_content(obj)

    # ------------------------------------------------------------------
    # Stream header
    # ------------------------------------------------------------------

    def _write_header(self) -> None:
        self._fd.write(
            struct.pack(
                ">HH",
                int(StreamConstants.STREAM_MAGIC),
                int(StreamConstants.STREAM_VERSION),
            )
        )

    # ------------------------------------------------------------------
    # Handle management
    # ------------------------------------------------------------------

    def _alloc_handle(self, obj: Any) -> int:
        """Allocates and records the next handle for *obj*."""
        h = self._next_handle
        self._next_handle += 1
        self._handle_map[id(obj)] = h
        _log.debug("Allocated handle 0x%x for %s", h, type(obj).__name__)
        return h

    def _try_reference(self, obj: Any) -> bool:
        """
        Emits ``TC_REFERENCE`` for *obj* if it was already written.

        :return: ``True`` when a reference was written and the caller must
                 **not** write the object again; ``False`` otherwise.
        """
        h = self._handle_map.get(id(obj))
        if h is None:
            return False
        _log.debug("TC_REFERENCE 0x%x for %s", h, type(obj).__name__)
        self._fd.write(struct.pack(">Bi", int(TerminalCode.TC_REFERENCE), h))
        return True

    # ------------------------------------------------------------------
    # Content dispatcher
    # ------------------------------------------------------------------

    def _write_content(self, obj: ParsedContent) -> None:
        """Writes a single content item — any valid v3 bean or ``None``."""
        match obj:
            case None:
                self._write_null()
            case JavaInstance():
                self._write_instance(obj)
            case JavaArray():
                self._write_array(obj)
            case JavaString():
                self._write_string_obj(obj)
            case JavaEnum():
                self._write_enum(obj)
            case JavaClass():
                self._write_class(obj)
            case BlockData():
                self._write_blockdata(obj)
            case JavaClassDesc():
                # A bare class descriptor written directly to the stream
                # (rare but valid at the top level).
                self._write_classdesc(obj)
            case _:
                raise UnsupportedFeatureError(f"Cannot serialize object of type {type(obj).__name__!r}")

    # ------------------------------------------------------------------
    # TC_NULL
    # ------------------------------------------------------------------

    def _write_null(self) -> None:
        self._fd.write(bytes([int(TerminalCode.TC_NULL)]))

    # ------------------------------------------------------------------
    # TC_OBJECT
    # ------------------------------------------------------------------

    def _write_instance(self, instance: JavaInstance) -> None:
        if self._try_reference(instance):
            return
        self._fd.write(bytes([int(TerminalCode.TC_OBJECT)]))
        self._write_classdesc(instance.classdesc)
        self._alloc_handle(instance)
        self._write_class_data(instance)

    # ------------------------------------------------------------------
    # TC_ARRAY
    # ------------------------------------------------------------------

    def _write_array(self, array: JavaArray) -> None:
        if self._try_reference(array):
            return
        self._fd.write(bytes([int(TerminalCode.TC_ARRAY)]))
        self._write_classdesc(array.classdesc)
        self._alloc_handle(array)

        data = array.data
        self._fd.write(struct.pack(">i", len(data)))

        et = array.element_type
        if et == FieldType.BYTE:
            # Bulk write: data is already bytes (or bytearray)
            self._fd.write(data if isinstance(data, (bytes, bytearray)) else bytes(data))  # type: ignore[arg-type]
        else:
            for item in data:  # type: ignore[union-attr]
                self._write_field_value(et, item)

    # ------------------------------------------------------------------
    # TC_STRING / TC_LONGSTRING
    # ------------------------------------------------------------------

    def _write_string_obj(self, s: JavaString) -> None:
        if self._try_reference(s):
            return
        encoded = _encode_mutf8(s.value)
        n = len(encoded)
        if n <= 0xFFFF:
            self._fd.write(bytes([int(TerminalCode.TC_STRING)]))
            self._alloc_handle(s)
            self._fd.write(struct.pack(">H", n) + encoded)
        else:
            self._fd.write(bytes([int(TerminalCode.TC_LONGSTRING)]))
            self._alloc_handle(s)
            self._fd.write(struct.pack(">q", n) + encoded)

    # ------------------------------------------------------------------
    # TC_ENUM
    # ------------------------------------------------------------------

    def _write_enum(self, enum: JavaEnum) -> None:
        if self._try_reference(enum):
            return
        self._fd.write(bytes([int(TerminalCode.TC_ENUM)]))
        self._write_classdesc(enum.classdesc)
        self._alloc_handle(enum)
        self._write_string_obj(enum.constant)

    # ------------------------------------------------------------------
    # TC_CLASS
    # ------------------------------------------------------------------

    def _write_class(self, cls: JavaClass) -> None:
        if self._try_reference(cls):
            return
        self._fd.write(bytes([int(TerminalCode.TC_CLASS)]))
        self._write_classdesc(cls.classdesc)
        self._alloc_handle(cls)

    # ------------------------------------------------------------------
    # TC_CLASSDESC / TC_PROXYCLASSDESC
    # ------------------------------------------------------------------

    def _write_classdesc(self, cd: JavaClassDesc | None) -> None:
        if cd is None:
            self._write_null()
            return
        if self._try_reference(cd):
            return
        match cd.class_type:
            case ClassDescType.NORMALCLASS:
                self._write_normal_classdesc(cd)
            case ClassDescType.PROXYCLASS:
                self._write_proxy_classdesc(cd)

    def _write_normal_classdesc(self, cd: JavaClassDesc) -> None:
        """
        Serializes a normal (non-proxy) class descriptor.

        Wire layout::

            TC_CLASSDESC utf(className) long(serialVersionUID)
            newHandle byte(classDescFlags) short(fieldCount)
            [byte(typeCode) utf(fieldName) [string(className2)]] ...
            classAnnotation superClassDesc
        """
        self._fd.write(bytes([int(TerminalCode.TC_CLASSDESC)]))
        self._write_utf(cd.name)
        self._fd.write(struct.pack(">q", cd.serial_version_uid))
        self._alloc_handle(cd)
        self._fd.write(struct.pack(">Bh", cd.desc_flags, len(cd.fields)))

        for f in cd.fields:
            # type byte + field name
            self._fd.write(bytes([f.type.value]))
            self._write_utf(f.name)
            # Object/array fields carry a second string: the class name
            if f.type in (FieldType.OBJECT, FieldType.ARRAY):
                cn = f.class_name or ""
                # Reuse the same JavaString object for identical class names
                # so that TC_REFERENCE is written on subsequent occurrences.
                if cn not in self._classname_strings:
                    self._classname_strings[cn] = JavaString(handle=0, value=cn)
                self._write_string_obj(self._classname_strings[cn])

        # Class annotations written by annotateClass() (usually empty)
        for ann in cd.annotations:
            self._write_content(ann)
        self._fd.write(bytes([int(TerminalCode.TC_ENDBLOCKDATA)]))

        # Super-class descriptor (or TC_NULL)
        self._write_classdesc(cd.super_class)

    def _write_proxy_classdesc(self, cd: JavaClassDesc) -> None:
        """
        Serializes a dynamic proxy class descriptor.

        Wire layout::

            TC_PROXYCLASSDESC int(interfaceCount)
            [utf(interfaceName)] ...
            newHandle classAnnotation superClassDesc
        """
        self._fd.write(bytes([int(TerminalCode.TC_PROXYCLASSDESC)]))
        self._fd.write(struct.pack(">i", len(cd.interfaces)))
        for iface in cd.interfaces:
            self._write_utf(iface)
        self._alloc_handle(cd)

        for ann in cd.annotations:
            self._write_content(ann)
        self._fd.write(bytes([int(TerminalCode.TC_ENDBLOCKDATA)]))

        self._write_classdesc(cd.super_class)

    # ------------------------------------------------------------------
    # TC_BLOCKDATA / TC_BLOCKDATALONG
    # ------------------------------------------------------------------

    def _write_blockdata(self, bd: BlockData) -> None:
        n = len(bd.data)
        if n <= 255:
            self._fd.write(struct.pack(">BB", int(TerminalCode.TC_BLOCKDATA), n))
        else:
            self._fd.write(struct.pack(">Bi", int(TerminalCode.TC_BLOCKDATALONG), n))
        self._fd.write(bd.data)

    # ------------------------------------------------------------------
    # classdata — instance field values + annotations per hierarchy class
    # ------------------------------------------------------------------

    def _write_class_data(self, instance: JavaInstance) -> None:
        """
        Writes all field values and object annotations for *instance*,
        walking the class hierarchy from topmost ancestor to concrete class
        (the same order as ``ObjectOutputStream`` on the Java side).
        """
        if instance.classdesc is None:
            return

        for cd in instance.classdesc.get_hierarchy():
            try:
                data_type = cd.data_type
            except ValueError:
                # No SC_SERIALIZABLE / SC_EXTERNALIZABLE flags — skip.
                continue

            cd_fields = instance.field_data.get(cd, {})

            match data_type:
                case ClassDataType.NOWRCLASS:
                    # Plain serializable class: write fields only.
                    for f in cd.fields:
                        self._write_field_value(f.type, cd_fields.get(f))

                case ClassDataType.WRCLASS:
                    # Serializable class with writeObject():
                    # fields first, then the custom annotation block.
                    for f in cd.fields:
                        self._write_field_value(f.type, cd_fields.get(f))
                    for ann in instance.annotations.get(cd, []):
                        self._write_content(ann)
                    self._fd.write(bytes([int(TerminalCode.TC_ENDBLOCKDATA)]))

                case ClassDataType.OBJECT_ANNOTATION:
                    # Externalizable + SC_BLOCK_DATA:
                    # all data lives in the annotation block.
                    for ann in instance.annotations.get(cd, []):
                        self._write_content(ann)
                    self._fd.write(bytes([int(TerminalCode.TC_ENDBLOCKDATA)]))

                case ClassDataType.EXTERNAL_CONTENTS:
                    raise UnsupportedFeatureError(
                        f"SC_EXTERNALIZABLE without SC_BLOCK_DATA "
                        f"(Protocol v1) is not supported for class {cd.name!r}"
                    )

    # ------------------------------------------------------------------
    # Field value writer
    # ------------------------------------------------------------------

    def _write_field_value(self, field_type: FieldType, value: Any) -> None:
        """Writes a single field value according to *field_type*."""
        match field_type:
            case FieldType.BYTE:
                self._fd.write(struct.pack(">b", int(value) if value is not None else 0))
            case FieldType.CHAR:
                cp = ord(value) if isinstance(value, str) else int(value)
                self._fd.write(struct.pack(">H", cp & 0xFFFF))
            case FieldType.SHORT:
                self._fd.write(struct.pack(">h", int(value) if value is not None else 0))
            case FieldType.INTEGER:
                self._fd.write(struct.pack(">i", int(value) if value is not None else 0))
            case FieldType.LONG:
                self._fd.write(struct.pack(">q", int(value) if value is not None else 0))
            case FieldType.FLOAT:
                self._fd.write(struct.pack(">f", float(value) if value is not None else 0.0))
            case FieldType.DOUBLE:
                self._fd.write(struct.pack(">d", float(value) if value is not None else 0.0))
            case FieldType.BOOLEAN:
                self._fd.write(bytes([1 if value else 0]))
            case FieldType.OBJECT | FieldType.ARRAY:
                self._write_content(value)

    # ------------------------------------------------------------------
    # Short-length UTF helper
    # ------------------------------------------------------------------

    def _write_utf(self, s: str) -> None:
        """
        Writes a "short" UTF entry: 2-byte unsigned length + Modified UTF-8
        bytes.

        Used for class names, field names, and interface names *inside* class
        descriptor records.  These strings do **not** receive handles and are
        **not** written as ``TC_STRING`` objects.

        :raises ValueError: If the encoded byte length exceeds 65535.
        """
        encoded = _encode_mutf8(s)
        n = len(encoded)
        if n > 0xFFFF:
            raise ValueError(f"String too long for short-length UTF field: {n} bytes (max 65535)")
        self._fd.write(struct.pack(">H", n) + encoded)


# ------------------------------------------------------------------------------
# Module-level convenience functions
# ------------------------------------------------------------------------------


def dump(fd: IO[bytes], *objects: ParsedContent) -> None:
    """
    Serializes one or more v3 bean objects to a binary file-like object.

    :param fd: A writable binary stream (opened in ``"wb"`` mode).
    :param objects: Top-level objects to serialize.  Pass several to create a
                    multi-object stream (each requiring a separate
                    ``readObject()`` call on the Java side).
    :raises UnsupportedFeatureError: If an object type cannot be serialized.
    """
    writer = JavaStreamWriter(fd)
    writer.write_stream(*objects)


def dumps(*objects: ParsedContent) -> bytes:
    """
    Serializes one or more v3 bean objects to a :class:`bytes` object.

    :param objects: Top-level objects to serialize (see :func:`dump`).
    :return: A complete Java Object Serialization stream as :class:`bytes`.
    :raises UnsupportedFeatureError: If an object type cannot be serialized.
    """
    buf = BytesIO()
    dump(buf, *objects)
    return buf.getvalue()
