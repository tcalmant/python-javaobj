#!/usr/bin/env python3
"""
Parser for the Java Object Serialization stream format (v3)

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
from typing import IO, Any

# Javaobj
from ..constants import (
    ClassDescFlags,
    StreamConstants,
    TerminalCode,
    TypeCode,
)
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
    ParseError,
    SecurityError,
    UnexpectedOpcodeError,
    UnsupportedFeatureError,
)
from .reader import DataReader
from .transformers import DefaultObjectTransformer, ObjectTransformer

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 5, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------

__all__ = ["JavaStreamParser"]

_log = logging.getLogger("javaobj.v3.parser")


class _ExceptionRead(Exception):
    """Internal signal: a TC_EXCEPTION object was parsed and should propagate."""

    def __init__(self, content: JavaInstance) -> None:
        self.exception_object = content


class JavaStreamParser:
    """
    Stateful parser for the Java Object Serialization stream format.

    Usage::

        parser = JavaStreamParser(fd, transformers)
        contents = parser.run()

    Parameters
    ----------
    fd:
        A readable binary file-like object positioned at the start of a Java
        serialized stream (magic ``0xACED``).
    transformers:
        Ordered list of :class:`~javaobj.v3.transformers.ObjectTransformer`
        instances.  Transformers are tried in order; the first one that
        returns a non-``None`` result wins.
    max_array_size:
        Maximum number of bytes allocatable by a single array or bulk-read
        operation.  Raises :class:`~javaobj.v3.exceptions.SecurityError` on
        breach.
    max_depth:
        Maximum recursion depth of the parse tree.  Raises
        :class:`~javaobj.v3.exceptions.SecurityError` on breach.
    """

    def __init__(
        self,
        fd: IO[bytes],
        transformers: list[ObjectTransformer],
        *,
        max_array_size: int = DataReader.DEFAULT_MAX_ARRAY_SIZE,
        max_depth: int = DataReader.DEFAULT_MAX_DEPTH,
    ) -> None:
        self._fd = fd
        self._reader = DataReader(
            fd,
            max_array_size=max_array_size,
            max_string_size=max_array_size,
        )
        self._transformers = list(transformers)
        self._max_depth = max_depth

        # Handle table: maps handle int → ParsedContent
        self._handles: dict[int, ParsedContent] = {}
        # Saved handle snapshots from TC_RESET events
        self._handle_maps: list[dict[int, ParsedContent]] = []
        self._current_handle = int(StreamConstants.BASE_REFERENCE_IDX)

        # Current recursion depth
        self._depth = 0

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> list[ParsedContent]:
        """
        Parses the stream and returns a list of top-level content objects.

        :raises ParseError: On malformed stream data.
        :raises SecurityError: If a configured limit is breached.
        :raises UnsupportedFeatureError: If an unimplemented feature is used.
        """
        magic = self._reader.read_ushort()
        if magic != StreamConstants.STREAM_MAGIC:
            raise ParseError(f"Invalid stream magic: 0x{magic:04x} (expected 0xACED)", 0)
        version = self._reader.read_ushort()
        if version != StreamConstants.STREAM_VERSION:
            raise ParseError(
                f"Unsupported stream version: 0x{version:04x} "
                f"(expected 0x{int(StreamConstants.STREAM_VERSION):04x})",
                2,
            )

        self._reset()
        contents: list[ParsedContent] = []

        while True:
            try:
                opcode = self._reader.read_ubyte()
            except EOFError:
                break

            if opcode == TerminalCode.TC_RESET:
                self._reset()
                continue

            start_offset = self._reader.offset - 1
            item = self._read_content(opcode, block_data_allowed=True)

            if isinstance(item, JavaInstance) and item.is_exception:
                # Wrap exception instances together with their raw bytes.
                end_offset = self._reader.offset
                self._fd.seek(start_offset)
                raw = self._fd.read(end_offset - start_offset)
                item = ExceptionState(
                    exception_object=item,
                    stream_data=raw,
                    handle=item.handle,
                )

            contents.append(item)

        if self._handles:
            self._handle_maps.append(dict(self._handles))

        return contents

    # ------------------------------------------------------------------
    # Internal state management
    # ------------------------------------------------------------------

    def _reset(self) -> None:
        """Saves the current handle map and starts a fresh one (TC_RESET)."""
        if self._handles:
            self._handle_maps.append(dict(self._handles))
        self._handles.clear()
        self._current_handle = int(StreamConstants.BASE_REFERENCE_IDX)

    def _new_handle(self) -> int:
        """Allocates and returns the next handle value."""
        h = self._current_handle
        self._current_handle += 1
        return h

    def _set_handle(self, handle: int, obj: ParsedContent) -> None:
        """Stores *obj* under *handle* in the current handle table."""
        if handle in self._handles:
            raise ParseError(f"Duplicate handle 0x{handle:x}", self._reader.offset)
        self._handles[handle] = obj

    # ------------------------------------------------------------------
    # Content dispatcher
    # ------------------------------------------------------------------

    def _read_content(
        self,
        opcode: int,
        *,
        block_data_allowed: bool,
        class_desc: JavaClassDesc | None = None,
    ) -> ParsedContent:
        """
        Dispatches *opcode* to the appropriate ``_do_*`` method.

        :param opcode: The TC_* byte already read from the stream.
        :param block_data_allowed: Whether TC_BLOCKDATA records are valid here.
        :param class_desc: Optional context class (for WRCLASS custom reading).
        :raises SecurityError: If the maximum recursion depth is exceeded.
        :raises ParseError: On unrecognised opcode.
        """
        self._depth += 1
        if self._depth > self._max_depth:
            raise SecurityError(
                f"Maximum parse depth ({self._max_depth}) exceeded at offset 0x{self._reader.offset:x}"
            )
        try:
            match opcode:
                case TerminalCode.TC_NULL:
                    return None
                case TerminalCode.TC_OBJECT:
                    return self._do_object()
                case TerminalCode.TC_CLASS:
                    return self._do_class()
                case TerminalCode.TC_ARRAY:
                    return self._do_array()
                case (TerminalCode.TC_STRING | TerminalCode.TC_LONGSTRING) as str_code:
                    return self._do_string(str_code)
                case TerminalCode.TC_ENUM:
                    return self._do_enum()
                case (TerminalCode.TC_CLASSDESC | TerminalCode.TC_PROXYCLASSDESC) as cd_code:
                    return self._do_classdesc(cd_code)
                case TerminalCode.TC_REFERENCE:
                    return self._do_reference()
                case TerminalCode.TC_EXCEPTION:
                    return self._do_exception()
                case (TerminalCode.TC_BLOCKDATA | TerminalCode.TC_BLOCKDATALONG) as bd_code:
                    if not block_data_allowed:
                        raise ParseError(
                            "Unexpected TC_BLOCKDATA where not allowed",
                            self._reader.offset,
                        )
                    return self._do_block_data(bd_code)
                case _:
                    # Last resort: check whether a transformer can handle
                    # a custom writeObject for the active class_desc.
                    if (
                        class_desc is not None
                        and class_desc.name
                        and class_desc.data_type == ClassDataType.WRCLASS
                    ):
                        # Rewind one byte so the transformer sees the opcode.
                        self._fd.seek(-1, 1)
                        result = self._custom_read_object(class_desc.name)
                        if result is not None:
                            return result

                    raise ParseError(
                        f"Unknown opcode 0x{opcode:02x}",
                        self._reader.offset,
                    )
        finally:
            self._depth -= 1

    # ------------------------------------------------------------------
    # TC_OBJECT
    # ------------------------------------------------------------------

    def _do_object(self) -> JavaInstance:
        """Parses a TC_OBJECT record and returns a :class:`JavaInstance`."""
        classdesc = self._read_classdesc()

        handle = self._new_handle()
        _log.debug("TC_OBJECT handle=0x%x class=%s", handle, classdesc)

        instance = self._create_instance(classdesc)
        instance.classdesc = classdesc
        instance.handle = handle

        self._set_handle(handle, instance)
        self._read_class_data(instance)
        instance.load_from_instance()

        _log.debug("Done reading object handle=0x%x", handle)
        return instance

    def _create_instance(self, classdesc: JavaClassDesc | None) -> JavaInstance:
        """
        Tries each transformer in order; falls back to plain JavaInstance.
        """
        if classdesc is not None and classdesc.name:
            for t in self._transformers:
                inst = t.create_instance(classdesc)
                if inst is not None:
                    return inst
        return JavaInstance()

    # ------------------------------------------------------------------
    # TC_CLASS
    # ------------------------------------------------------------------

    def _do_class(self) -> JavaClass:
        """Parses a TC_CLASS record."""
        classdesc = self._read_classdesc()
        if classdesc is None:
            raise ParseError("TC_CLASS requires a non-null class descriptor", self._reader.offset)
        handle = self._new_handle()
        obj = JavaClass(handle=handle, classdesc=classdesc)
        self._set_handle(handle, obj)
        return obj

    # ------------------------------------------------------------------
    # TC_ARRAY
    # ------------------------------------------------------------------

    def _do_array(self) -> JavaArray:
        """Parses a TC_ARRAY record."""
        classdesc = self._read_classdesc()
        if classdesc is None:
            raise ParseError("TC_ARRAY requires a non-null class descriptor", self._reader.offset)
        handle = self._new_handle()

        name = classdesc.name or ""
        if len(name) < 2:
            raise ParseError(
                f"Array class desc has invalid name {name!r}",
                self._reader.offset,
            )

        # The second character of the class name encodes the element type.
        element_type_byte = ord(name[1].encode("latin-1"))
        try:
            element_type = FieldType(element_type_byte)
        except ValueError:
            raise ParseError(
                f"Unknown array element type byte 0x{element_type_byte:02x}",
                self._reader.offset,
            )

        size = self._reader.read_int()
        if size < 0:
            raise ParseError(f"Invalid array size {size}", self._reader.offset)

        # Try transformers first (e.g. NumpyArrayTransformer)
        type_code = TypeCode(element_type_byte)
        data: bytes | list[Any] | None = None
        for t in self._transformers:
            data = t.load_array(self._reader, type_code, size)
            if data is not None:
                break

        if data is None:
            if element_type == FieldType.BYTE:
                # Efficient bulk read for byte arrays
                data = self._reader.read_bytes(size)
            else:
                data = [self._read_field_value(element_type) for _ in range(size)]

        array = JavaArray(
            handle=handle,
            classdesc=classdesc,
            element_type=element_type,
            data=data,
        )
        self._set_handle(handle, array)
        return array

    # ------------------------------------------------------------------
    # TC_STRING / TC_LONGSTRING
    # ------------------------------------------------------------------

    def _do_string(self, opcode: int) -> JavaString:
        """Parses a TC_STRING or TC_LONGSTRING record."""
        handle = self._new_handle()

        if opcode == TerminalCode.TC_STRING:
            value = self._reader.read_utf()
        elif opcode == TerminalCode.TC_LONGSTRING:
            value = self._reader.read_long_utf()
        else:
            raise ParseError(
                f"Expected TC_STRING or TC_LONGSTRING, got 0x{opcode:02x}",
                self._reader.offset,
            )

        java_str = JavaString(handle=handle, value=value)
        self._set_handle(handle, java_str)
        return java_str

    # ------------------------------------------------------------------
    # Helper: read a string that may be TC_STRING, TC_LONGSTRING or TC_REFERENCE
    # ------------------------------------------------------------------

    def _read_new_string(self, opcode: int) -> JavaString:
        """
        Reads a string-valued token; handles TC_REFERENCE to an earlier string.
        """
        if opcode == TerminalCode.TC_REFERENCE:
            prev = self._do_reference()
            if not isinstance(prev, JavaString):
                raise ParseError(
                    "TC_REFERENCE in string context does not point to a string",
                    self._reader.offset,
                )
            return prev
        return self._do_string(opcode)

    # ------------------------------------------------------------------
    # TC_ENUM
    # ------------------------------------------------------------------

    def _do_enum(self) -> JavaEnum:
        """Parses a TC_ENUM record."""
        classdesc = self._read_classdesc()
        if classdesc is None:
            raise ParseError("TC_ENUM has null class descriptor", self._reader.offset)

        handle = self._new_handle()

        str_opcode = self._reader.read_ubyte()
        constant = self._read_new_string(str_opcode)
        if classdesc.name:
            classdesc.enum_constants.add(constant.value)

        enum_obj = JavaEnum(handle=handle, classdesc=classdesc, constant=constant)
        self._set_handle(handle, enum_obj)
        return enum_obj

    # ------------------------------------------------------------------
    # TC_CLASSDESC / TC_PROXYCLASSDESC
    # ------------------------------------------------------------------

    def _read_classdesc(self) -> JavaClassDesc | None:
        """
        Reads a type-code byte then delegates to :meth:`_do_classdesc`.
        Returns ``None`` for TC_NULL.
        """
        opcode = self._reader.read_ubyte()
        return self._do_classdesc(opcode)

    def _do_classdesc(self, opcode: int) -> JavaClassDesc | None:
        """Parses a class descriptor record identified by *opcode*."""
        if opcode == TerminalCode.TC_NULL:
            return None

        if opcode == TerminalCode.TC_REFERENCE:
            prev = self._do_reference()
            if not isinstance(prev, JavaClassDesc):
                raise ParseError(
                    "TC_REFERENCE in classdesc context does not point to a class descriptor",
                    self._reader.offset,
                )
            return prev

        if opcode == TerminalCode.TC_CLASSDESC:
            return self._read_normal_classdesc()

        if opcode == TerminalCode.TC_PROXYCLASSDESC:
            return self._read_proxy_classdesc()

        raise UnexpectedOpcodeError(
            (
                TerminalCode.TC_NULL,
                TerminalCode.TC_REFERENCE,
                TerminalCode.TC_CLASSDESC,
                TerminalCode.TC_PROXYCLASSDESC,
            ),
            opcode,
            self._reader.offset,
        )

    def _read_normal_classdesc(self) -> JavaClassDesc:
        """Parses a TC_CLASSDESC record (after the opcode byte)."""
        name = self._reader.read_utf()
        serial_version_uid = self._reader.read_long()
        handle = self._new_handle()
        desc_flags = self._reader.read_ubyte()

        nb_fields = self._reader.read_short()
        if nb_fields < 0:
            raise ParseError(f"Invalid field count {nb_fields}", self._reader.offset)

        fields: list[JavaField] = []
        for _ in range(nb_fields):
            field_type_byte = self._reader.read_ubyte()
            try:
                field_type = FieldType(field_type_byte)
            except ValueError:
                raise ParseError(
                    f"Unknown field type byte 0x{field_type_byte:02x}",
                    self._reader.offset,
                )
            field_name = self._reader.read_utf()
            class_name: str | None = None

            if field_type_byte in (TypeCode.TYPE_OBJECT, TypeCode.TYPE_ARRAY):
                str_opcode = self._reader.read_ubyte()
                class_name_str = self._read_new_string(str_opcode)
                class_name = class_name_str.value

            fields.append(JavaField(type=field_type, name=field_name, class_name=class_name))

        classdesc = JavaClassDesc(
            handle=handle,
            name=name,
            serial_version_uid=serial_version_uid,
            desc_flags=desc_flags,
            class_type=ClassDescType.NORMALCLASS,
            fields=fields,
        )
        self._set_handle(handle, classdesc)

        classdesc.annotations = self._read_class_annotations()
        classdesc.super_class = self._read_classdesc()
        if classdesc.super_class is not None:
            classdesc.super_class.is_super_class = True

        return classdesc

    def _read_proxy_classdesc(self) -> JavaClassDesc:
        """Parses a TC_PROXYCLASSDESC record (after the opcode byte)."""
        handle = self._new_handle()
        nb_interfaces = self._reader.read_int()
        interfaces = [self._reader.read_utf() for _ in range(nb_interfaces)]

        # Proxy classes are treated as Serializable with SC_SERIALIZABLE flag.
        desc_flags = ClassDescFlags.SC_SERIALIZABLE | ClassDescFlags.SC_WRITE_METHOD
        classdesc = JavaClassDesc(
            handle=handle,
            name="",
            serial_version_uid=0,
            desc_flags=int(desc_flags),
            class_type=ClassDescType.PROXYCLASS,
            interfaces=interfaces,
        )
        self._set_handle(handle, classdesc)

        classdesc.annotations = self._read_class_annotations()
        classdesc.super_class = self._read_classdesc()
        if classdesc.super_class is not None:
            classdesc.super_class.is_super_class = True

        return classdesc

    # ------------------------------------------------------------------
    # TC_REFERENCE
    # ------------------------------------------------------------------

    def _do_reference(self) -> ParsedContent:
        """Resolves a TC_REFERENCE to a previously parsed object."""
        handle = self._reader.read_int()
        try:
            return self._handles[handle]
        except KeyError:
            raise ParseError(f"Invalid handle 0x{handle:x}", self._reader.offset)

    # ------------------------------------------------------------------
    # TC_EXCEPTION
    # ------------------------------------------------------------------

    def _do_exception(self) -> JavaInstance:
        """
        Reads a TC_EXCEPTION record.

        The stream resets its state, parses one object (the exception), then
        resets again.
        """
        self._reset()
        opcode = self._reader.read_ubyte()
        if opcode == TerminalCode.TC_RESET:
            raise ParseError(
                "TC_RESET encountered while reading a TC_EXCEPTION",
                self._reader.offset,
            )

        content = self._read_content(opcode, block_data_allowed=False)
        if content is None:
            raise ParseError("TC_EXCEPTION contains a null object", self._reader.offset)
        if not isinstance(content, JavaInstance):
            raise ParseError("TC_EXCEPTION object is not a Java instance", self._reader.offset)
        content.is_exception = True
        self._reset()
        return content

    # ------------------------------------------------------------------
    # TC_BLOCKDATA / TC_BLOCKDATALONG
    # ------------------------------------------------------------------

    def _do_block_data(self, opcode: int) -> BlockData:
        """Reads a TC_BLOCKDATA or TC_BLOCKDATALONG record."""
        if opcode == TerminalCode.TC_BLOCKDATA:
            size = self._reader.read_ubyte()
        elif opcode == TerminalCode.TC_BLOCKDATALONG:
            size = self._reader.read_int()
        else:
            raise ParseError(
                f"Expected block-data opcode, got 0x{opcode:02x}",
                self._reader.offset,
            )

        if size < 0:
            raise ParseError(f"Invalid block data size {size}", self._reader.offset)

        data = self._reader.read_bytes(size)
        return BlockData(data=data)

    # ------------------------------------------------------------------
    # Class annotations (written by writeObject / annotateClass)
    # ------------------------------------------------------------------

    def _read_class_annotations(self, class_desc: JavaClassDesc | None = None) -> list[ParsedContent]:
        """
        Reads annotation objects until TC_ENDBLOCKDATA is encountered.

        :param class_desc: Optional context used for WRCLASS custom readers.
        :return: List of annotation content items (may be empty).
        """
        items: list[ParsedContent] = []
        while True:
            opcode = self._reader.read_ubyte()

            if opcode == TerminalCode.TC_ENDBLOCKDATA:
                return items

            if opcode == TerminalCode.TC_RESET:
                self._reset()
                continue

            try:
                item = self._read_content(
                    opcode,
                    block_data_allowed=True,
                    class_desc=class_desc,
                )
            except _ExceptionRead as exc:
                raise _ExceptionRead(exc.exception_object) from None

            if isinstance(item, JavaInstance) and item.is_exception:
                raise _ExceptionRead(item)

            items.append(item)

    # ------------------------------------------------------------------
    # Instance data (classdata)
    # ------------------------------------------------------------------

    def _read_class_data(self, instance: JavaInstance) -> None:
        """
        Reads all field data and annotations for *instance* according to
        its class hierarchy.
        """
        if instance.classdesc is None:
            return

        hierarchy = instance.classdesc.get_hierarchy()
        field_data: dict[JavaClassDesc, dict[JavaField, Any]] = {}
        annotations: dict[JavaClassDesc, list[ParsedContent]] = {}

        for cd in hierarchy:
            values: dict[JavaField, Any] = {}

            try:
                data_type = cd.data_type
            except ValueError:
                # Skip class descs with no serializable/externalizable flags
                # (e.g. proxy classes that appear in super-class chains).
                continue

            match data_type:
                case ClassDataType.NOWRCLASS:
                    for f in cd.fields:
                        values[f] = self._read_field_value(f.type)
                    field_data[cd] = values

                case ClassDataType.WRCLASS:
                    # Read the default serializable fields first …
                    for f in cd.fields:
                        values[f] = self._read_field_value(f.type)
                    field_data[cd] = values
                    # … then read the custom writeObject annotation block.
                    # load_from_instance() on the JavaInstance (or transformer
                    # subclass) will process these annotations afterwards.
                    annotations[cd] = self._read_class_annotations(cd)

                case ClassDataType.OBJECT_ANNOTATION:
                    # SC_EXTERNALIZABLE + SC_BLOCK_DATA
                    if not instance.load_from_blockdata(self, self._reader):
                        raise ParseError(
                            f"Externalizable class {cd.name!r} with "
                            "SC_BLOCK_DATA cannot be parsed: no transformer "
                            "handled load_from_blockdata()",
                            self._reader.offset,
                        )
                    annotations[cd] = self._read_class_annotations(cd)

                case ClassDataType.EXTERNAL_CONTENTS:
                    # SC_EXTERNALIZABLE without SC_BLOCK_DATA (Protocol v1).
                    raise UnsupportedFeatureError(
                        f"SC_EXTERNALIZABLE without SC_BLOCK_DATA "
                        f"(Protocol v1) is not supported for class "
                        f"{cd.name!r}. "
                        "This stream was likely produced with an old JDK."
                    )

        instance.field_data = field_data
        instance.annotations = annotations

    def _is_default_supported(self, class_name: str) -> bool:
        """
        Returns ``True`` when the :class:`DefaultObjectTransformer` (if
        present) recognises *class_name*.
        """
        for t in self._transformers:
            if isinstance(t, DefaultObjectTransformer):
                return t.handles(class_name)
        return False

    # ------------------------------------------------------------------
    # Field value reader
    # ------------------------------------------------------------------

    def _read_field_value(self, field_type: FieldType) -> Any:
        """Reads and returns a single field value of the given type."""
        match field_type:
            case FieldType.BYTE:
                return self._reader.read_byte()
            case FieldType.CHAR:
                return self._reader.read_char()
            case FieldType.DOUBLE:
                return self._reader.read_double()
            case FieldType.FLOAT:
                return self._reader.read_float()
            case FieldType.INTEGER:
                return self._reader.read_int()
            case FieldType.LONG:
                return self._reader.read_long()
            case FieldType.SHORT:
                return self._reader.read_short()
            case FieldType.BOOLEAN:
                return self._reader.read_bool()
            case FieldType.OBJECT | FieldType.ARRAY as obj_type:
                sub_opcode = self._reader.read_ubyte()

                if obj_type == FieldType.ARRAY:
                    if sub_opcode == TerminalCode.TC_NULL:
                        return None
                    if sub_opcode == TerminalCode.TC_REFERENCE:
                        return self._do_reference()
                    if sub_opcode != TerminalCode.TC_ARRAY:
                        raise ParseError(
                            f"Expected TC_ARRAY for array field, got 0x{sub_opcode:02x}",
                            self._reader.offset,
                        )

                content = self._read_content(sub_opcode, block_data_allowed=False)
                if isinstance(content, JavaInstance) and content.is_exception:
                    raise _ExceptionRead(content)
                return content

        raise ParseError(
            f"Cannot read field of unknown type {field_type!r}",
            self._reader.offset,
        )

    # ------------------------------------------------------------------
    # Custom writeObject dispatcher
    # ------------------------------------------------------------------

    def _custom_read_object(self, class_name: str) -> Any | None:
        """
        Tries each transformer's ``load_custom_writeObject`` for *class_name*.
        Returns ``None`` if no transformer handles it.
        """
        for t in self._transformers:
            result = t.load_custom_writeObject(self, self._reader, class_name)
            if result is not None:
                return result
        return None
