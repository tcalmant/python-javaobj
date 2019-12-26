#!/usr/bin/env python3
"""
New core version of python-javaobj, using the same approach as jdeserialize
"""

from enum import Enum
from typing import Any, Callable, Dict, IO, List, Optional
import logging
import os
import struct

from .beans import *
from .constants import *
from ..modifiedutf8 import decode_modified_utf8


def load(fd: IO[bytes]) -> Any:
    """
    Parses the content of the given file
    """
    parser = JavaStreamParser(fd)
    return parser.run()


class JavaStreamParser:
    """
    Parses a Java stream
    """

    def __init__(self, fd: IO[bytes]):
        """
        :param fd: File-object to read from
        """
        # Input stream
        self.__fd = fd

        # Logger
        self._log = logging.getLogger("javaobj.parser")

        # Handles
        self.__handle_maps: List[Dict[int, Content]] = []
        self.__handles: Dict[int, Content] = {}

        # Initial handle value
        self.__current_handle = BASE_REFERENCE_IDX

        # Handlers
        self.__type_code_handlers: Dict[int, Callable[[int], Content]] = {
            TC_OBJECT: self._do_object,
            TC_CLASS: self._do_class,
            TC_ARRAY: self._do_array,
            TC_STRING: self._read_new_string,
            TC_LONGSTRING: self._read_new_string,
            TC_ENUM: self._do_enum,
            TC_CLASSDESC: self._do_classdesc,
            TC_PROXYCLASSDESC: self._do_classdesc,
            TC_REFERENCE: self._do_reference,
            TC_NULL: self._do_null,
            TC_EXCEPTION: self._do_exception,
            TC_BLOCKDATA: self._do_block_data,
            TC_BLOCKDATALONG: self._do_block_data,
        }

    def run(self) -> List[Content]:
        """
        Parses the input stream
        """
        # Check the magic byte
        magic = self._read_ushort()
        if magic != STREAM_MAGIC:
            raise ValueError("Invalid file magic: 0x{0:x}".format(magic))

        # Check the stream version
        version = self._read_ushort()
        if version != STREAM_VERSION:
            raise ValueError("Invalid file version: 0x{0:x}".format(version))

        # Reset internal state
        self._reset()

        # Read content
        contents: List[Content] = []
        while True:
            self._log.info("Reading next content")
            start = self.__fd.tell()
            try:
                type_code = self._read_byte()
            except EOFError:
                # End of file
                break

            if type_code == TC_RESET:
                # Explicit reset
                self._reset()
                continue

            parsed_content = self._read_content(type_code, True)
            self._log.debug("Read: %s", parsed_content)
            if parsed_content is not None and parsed_content.is_exception:
                # Get the raw data between the start of the object and our
                # current position
                end = self.__fd.tell()
                self.__fd.seek(start, os.SEEK_SET)
                stream_data = self.__fd.read(end - start)

                # Prepare an exception object
                parsed_content = ExceptionState(parsed_content, stream_data)

            contents.append(parsed_content)

        for content in self.__handles.values():
            content.validate()

        # TODO: connect member classes ? (see jdeserialize @ 864)

        if self.__handles:
            self.__handle_maps.append(self.__handles.copy())

        return contents

    def dump(self, content: List[Content]) -> str:
        """
        Dumps to a string the given objects
        """
        lines: List[str] = []

        # Stream content
        lines.append("//// BEGIN stream content output")
        lines.extend(str(c) for c in content)
        lines.append("//// END stream content output")
        lines.append("")

        lines.append("//// BEGIN instance dump")
        for c in self.__handles.values():
            if isinstance(c, JavaInstance):
                instance: JavaInstance = c
                lines.extend(self._dump_instance(instance))
        lines.append("//// END instance dump")
        lines.append("")
        return "\n".join(lines)

    def _dump_instance(self, instance: JavaInstance) -> List[str]:
        """
        Dumps an instance to a set of lines
        """
        lines: List[str] = []
        lines.append("[instance 0x{0:x}: 0x{1:x} / {2}".format(
            instance.handle, instance.classdesc.handle, instance.classdesc.name
        ))

        if instance.annotations:
            lines.append("\tobject annotations:")
            for cd, content in instance.annotations.items():
                lines.append("\t" + cd.name)
                for c in content:
                    lines.append("\t\t" + str(c))

        if instance.field_data:
            lines.append("\tfield data:")
            for field, obj in instance.field_data.items():
                line = "\t\t" + field.name + ": "
                if isinstance(obj, Content):
                    content: Content = obj
                    h = content.handle
                    if h == instance.handle:
                        line += "this"
                    else:
                        line += "r0x{0:x}".format(h)

                    line += ": " + str(c)
                else:
                    line += str(obj)

                lines.append(line)

        lines.append("]")
        return lines

    def _read(self, struct_format: str) -> List[Any]:
        """
        Reads from the input stream, using struct

        :param struct_format: An unpack format string
        :return: The result of struct.unpack (tuple)
        :raise RuntimeError: End of stream reached during unpacking
        """
        length = struct.calcsize(struct_format)
        bytes_array = self.__fd.read(length)

        if len(bytes_array) != length:
            raise EOFError("Stream has ended unexpectedly while parsing.")

        return struct.unpack(struct_format, bytes_array)

    def _read_bool(self) -> bool:
        """
        Shortcut to read a single `boolean` (1 byte)
        """
        return bool(self._read(">B")[0])

    def _read_byte(self) -> int:
        """
        Shortcut to read a single `byte` (1 byte)
        """
        return self._read(">b")[0]

    def _read_ubyte(self) -> int:
        """
        Shortcut to read an unsigned `byte` (1 byte)
        """
        return self._read(">B")[0]

    def _read_char(self) -> chr:
        """
        Shortcut to read a single `char` (2 bytes)
        """
        return chr(self._read(">H")[0])

    def _read_short(self) -> int:
        """
        Shortcut to read a single `short` (2 bytes)
        """
        return self._read(">h")[0]

    def _read_ushort(self) -> int:
        """
        Shortcut to read an unsigned `short` (2 bytes)
        """
        return self._read(">H")[0]

    def _read_int(self) -> int:
        """
        Shortcut to read a single `int` (4 bytes)
        """
        return self._read(">i")[0]

    def _read_float(self) -> float:
        """
        Shortcut to read a single `float` (4 bytes)
        """
        return self._read(">f")[0]

    def _read_long(self) -> int:
        """
        Shortcut to read a single `long` (8 bytes)
        """
        return self._read(">q")[0]

    def _read_double(self) -> float:
        """
        Shortcut to read a single `double` (8 bytes)
        """
        return self._read(">d")[0]

    def _read_UTF(self) -> str:
        """
        Reads a Java string
        """
        length = self._read_ushort()
        ba = self.__fd.read(length)
        return decode_modified_utf8(ba)[0]

    def _reset(self) -> None:
        """
        Resets the internal state of the parser
        """
        if self.__handles:
            self.__handle_maps.append(self.__handles.copy())

        self.__handles.clear()

        # Reset handle index
        self.__current_handle = BASE_REFERENCE_IDX

    def _new_handle(self) -> int:
        """
        Returns a new handle value
        """
        handle = self.__current_handle
        self.__current_handle += 1
        return handle

    def _set_handle(self, handle: int, content: Content) -> None:
        """
        Stores the reference to an object
        """
        if handle in self.__handles:
            raise ValueError("Trying to reset handle {0:x}".format(handle))

        self.__handles[handle] = content

    def _do_null(self, _) -> None:
        """
        The easiest one
        """
        return None

    def _read_content(self, type_code: int, block_data: bool) -> Content:
        """
        Parses the next content
        """
        if not block_data and type_code in (TC_BLOCKDATA, TC_BLOCKDATALONG):
            raise ValueError("Got a block data, but not allowed here.")

        try:
            handler = self.__type_code_handlers[type_code]
        except KeyError:
            raise ValueError("Unknown type code: 0x{0:x}".format(type_code))
        else:
            try:
                return handler(type_code)
            except ExceptionRead as ex:
                return ex.exception_object

    def _read_new_string(self, type_code: int) -> JavaString:
        """
        Reads a Java String
        """
        if type_code == TC_REFERENCE:
            # Got a reference
            previous = self._do_reference()
            if not isinstance(previous, JavaString):
                raise ValueError("Invalid reference to a Java string")
            return previous

        # Assign a new handle
        handle = self._new_handle()

        # Read the length
        if type_code == TC_STRING:
            length = self._read_ushort()
        elif type_code == TC_LONGSTRING:
            length = self._read_long()
            if length < 0 or length > 2147483647:
                raise ValueError("Invalid string length: {0}".format(length))
            elif length < 65536:
                self._log.warning("Small string stored as a long one")

        # Parse the content
        data = self.__fd.read(length)
        java_str = JavaString(handle, data)

        # Store the reference to the string
        self._set_handle(handle, java_str)
        return java_str

    def _read_classdesc(self) -> JavaClassDesc:
        """
        Reads a class description with its type code
        """
        type_code = self._read_byte()
        return self._do_classdesc(type_code)

    def _do_classdesc(
        self, type_code: int, must_be_new: bool = False
    ) -> JavaClassDesc:
        """
        Parses a class description

        :param must_be_new: Check if the class description is really a new one
        """
        if type_code == TC_CLASSDESC:
            # Do the real job
            name = self._read_UTF()
            serial_version_uid = self._read_long()
            handle = self._new_handle()
            desc_flags = self._read_byte()
            nb_fields = self._read_short()
            if nb_fields < 0:
                raise ValueError("Invalid field count: {0}".format(nb_fields))

            fields: List[JavaField] = []
            for _ in range(nb_fields):
                field_type = self._read_byte()
                if field_type in PRIMITIVE_TYPES:
                    # Primitive type
                    field_name = self._read_UTF()
                    fields.append(JavaField(FieldType(field_type), field_name))
                elif field_type in (TYPE_OBJECT, TYPE_ARRAY):
                    # Array or object type
                    field_name = self._read_UTF()
                    # String type code
                    str_type_code = self._read_byte()
                    class_name = self._read_new_string(str_type_code)
                    fields.append(
                        JavaField(
                            FieldType(field_type), field_name, class_name,
                        ),
                    )
                else:
                    raise ValueError(
                        "Invalid field type char: 0x{0:x}".format(field_type)
                    )

            # Setup the class description bean
            class_desc = JavaClassDesc(ClassDescType.NORMALCLASS)
            class_desc.name = name
            class_desc.serial_version_uid = serial_version_uid
            class_desc.handle = handle
            class_desc.desc_flags = desc_flags
            class_desc.fields = fields
            class_desc.annotations = self._read_class_annotations()
            class_desc.super_class = self._read_classdesc()

            # Store the reference to the parsed bean
            self._set_handle(handle, class_desc)
            return class_desc
        elif type_code == TC_NULL:
            # Null reference
            if must_be_new:
                raise ValueError("Got Null instead of a new class description")
            return None
        elif type_code == TC_REFERENCE:
            # Reference to an already loading class description
            if must_be_new:
                raise ValueError(
                    "Got a reference instead of a new class description"
                )

            previous = self._do_reference()
            if not isinstance(previous, JavaClassDesc):
                raise ValueError("Referenced object is not a class description")
            return previous
        elif type_code == TC_PROXYCLASSDESC:
            # Proxy class description
            handle = self._new_handle()
            nb_interfaces = self._read_int()
            interfaces = [self._read_UTF() for _ in range(nb_interfaces)]

            class_desc = JavaClassDesc(ClassDescType.PROXYCLASS)
            class_desc.handle = handle
            class_desc.interfaces = interfaces
            class_desc.annotations = self._read_class_annotations()
            class_desc.super_class = self._read_classdesc()

            # Store the reference to the parsed bean
            self._set_handle(handle, class_desc)
            return class_desc

        raise ValueError("Expected a valid class description starter")

    def _read_class_annotations(self) -> List[Content]:
        """
        Reads the annotations associated to a class
        """
        contents: List[Content] = []
        while True:
            type_code = self._read_byte()
            if type_code == TC_ENDBLOCKDATA:
                # We're done here
                return contents
            elif type_code == TC_RESET:
                # Reset references
                self._reset()
                continue

            java_object = self._read_content(type_code, True)
            if java_object is not None and java_object.is_exception:
                raise ExceptionRead(java_object)

            contents.append(java_object)

    def _do_object(self, type_code: int = 0) -> JavaInstance:
        """
        Parses an object
        """
        # Parse the object class description
        class_desc = self._read_classdesc()

        # Assign a new handle
        handle = self._new_handle()
        self._log.debug(
            "Reading new object: handle %x, classdesc %s", handle, class_desc
        )

        # Prepare the instance object
        instance = JavaInstance()
        instance.classdesc = class_desc
        instance.handle = handle

        # Store the instance
        self._set_handle(handle, instance)

        # Read the instance content
        self._read_class_data(instance)
        self._log.debug("Done reading object handle %x", handle)
        return instance

    def _read_class_data(self, instance: JavaInstance) -> None:
        """
        Reads the content of an instance
        """
        # Read the class hierarchy
        classes: List[JavaClassDesc] = []
        instance.classdesc.get_hierarchy(classes)

        all_data: Dict[JavaClassDesc, Dict[JavaField, Any]] = {}
        annotations: Dict[JavaClassDesc, List[Content]] = {}

        for cd in classes:
            values: Dict[JavaField, Any] = {}
            if cd.desc_flags & SC_SERIALIZABLE:
                if cd.desc_flags & SC_EXTERNALIZABLE:
                    raise ValueError(
                        "SC_EXTERNALIZABLE & SC_SERIALIZABLE encountered"
                    )

                for field in cd.fields:
                    values[field] = self._read_field_value(field.type)

                all_data[cd] = values

                if cd.desc_flags & SC_WRITE_METHOD:
                    if cd.desc_flags & SC_ENUM:
                        raise ValueError(
                            "SC_ENUM & SC_WRITE_METHOD encountered!"
                        )

                    annotations[cd] = self._read_class_annotations()
            elif cd.desc_flags & SC_EXTERNALIZABLE:
                if cd.desc_flags & SC_SERIALIZABLE:
                    raise ValueError(
                        "SC_EXTERNALIZABLE & SC_SERIALIZABLE encountered"
                    )

                if cd.desc_flags & SC_BLOCK_DATA:
                    raise ValueError(
                        "hit externalizable with nonzero SC_BLOCK_DATA; "
                        "can't interpret data"
                    )

                annotations[cd] = self._read_class_annotations()

        instance.annotations = annotations
        instance.field_data = all_data

    def _read_field_value(self, field_type: FieldType) -> Any:
        """
        Reads the value of an instance field
        """
        if field_type == FieldType.BYTE:
            return self._read_byte()
        elif field_type == FieldType.CHAR:
            return self._read_char()
        elif field_type == FieldType.DOUBLE:
            return self._read_double()
        elif field_type == FieldType.FLOAT:
            return self._read_float()
        elif field_type == FieldType.INTEGER:
            return self._read_int()
        elif field_type == FieldType.LONG:
            return self._read_long()
        elif field_type == FieldType.SHORT:
            return self._read_short()
        elif field_type == FieldType.BOOLEAN:
            return self._read_bool()
        elif field_type in (FieldType.OBJECT, FieldType.ARRAY):
            sub_type_code = self._read_byte()
            if field_type == FieldType.ARRAY and sub_type_code != TC_ARRAY:
                raise ValueError("Array type listed, but type code != TC_ARRAY")

            content = self._read_content(sub_type_code, False)
            if content is not None and content.is_exception:
                raise ExceptionRead(content)

            return content

        raise ValueError("Can't process type: {0}".format(field_type))

    def _do_reference(self, type_code: int = 0) -> Content:
        """
        Returns an object already parsed
        """
        handle = self._read_int()
        try:
            return self.__handles[handle]
        except KeyError:
            raise ValueError("Invalid reference handle: {0:x}".format(handle))

    def _do_enum(self, type_code: int) -> JavaEnum:
        """
        Parses an enumeration
        """
        cd = self._read_classdesc()
        if cd is None:
            raise ValueError("Enum description can't be null")

        handle = self._new_handle()

        # Read the enum string
        sub_type_code = self._read_byte()
        enum_str = self._read_new_string(sub_type_code)
        cd.enum_constants.add(enum_str.value)

        # Store the object
        self._set_handle(handle, enum_str)
        return JavaEnum(handle, cd, enum_str)

    def _do_class(self, type_code: int) -> JavaClass:
        """
        Parses a class
        """
        cd = self._read_classdesc()
        handle = self._new_handle()
        class_obj = JavaClass(handle, cd)

        # Store the class object
        self._set_handle(handle, class_obj)
        return class_obj

    def _do_array(self, type_code: int) -> JavaArray:
        """
        Parses an array
        """
        cd = self._read_classdesc()
        handle = self._new_handle()
        if len(cd.name) < 2:
            raise ValueError("Invalid name in array class description")

        # Content type
        content_type_byte = ord(cd.name[1].encode("latin1"))
        field_type = FieldType(content_type_byte)

        # Array size
        size = self._read_int()
        if size < 0:
            raise ValueError("Invalid array size")

        # Array content
        content = [self._read_field_value(field_type) for _ in range(size)]
        return JavaArray(handle, cd, field_type, content)

    def _do_exception(self, type_code: int) -> Content:
        """
        Read the content of a thrown exception
        """
        # Start by resetting current state
        self._reset()

        type_code = self._read_byte()
        if type_code == TC_RESET:
            raise ValueError("TC_RESET read while reading exception")

        content = self._read_content(type_code, False)
        if content is None:
            raise ValueError("Null exception object")

        if not isinstance(content, JavaInstance):
            raise ValueError("Exception object is not an instance")

        if content.is_exception:
            raise ExceptionRead(content)

        # Strange object ?
        content.is_exception = True
        self._reset()
        return content

    def _do_block_data(self, type_code: int) -> BlockData:
        """
        Reads a block data
        """
        # Parse the size
        if type_code == TC_BLOCKDATA:
            size = self._read_ubyte()
        elif type_code == TC_BLOCKDATALONG:
            size = self._read_int()
        else:
            raise ValueError("Invalid type code for blockdata")

        if size < 0:
            raise ValueError("Invalid value for block data size")

        # Read the block
        data = self.__fd.read(size)
        return BlockData(data)
