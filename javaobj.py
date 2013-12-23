#!/usr/bin/python
# -- Content-Encoding: UTF-8 --
"""
Provides functions for reading and writing (writing is WIP currently) Java
objects serialized or will be deserialized by ObjectOutputStream. This form of
object representation is a standard data interchange format in Java world.

javaobj module exposes an API familiar to users of the standard library marshal,
pickle and json modules.

See:
http://download.oracle.com/javase/6/docs/platform/serialization/spec/protocol.html

:authors: Volodymyr Buell, Thomas Calmant
:license: Apache License 2.0
:version: 0.1.1
:status: Alpha

..

    Copyright 2013 Thomas Calmant

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

# Module version
__version_info__ = (0, 1, 1)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------

# Standard library
import logging
import struct
import sys

if sys.version_info[0] < 3:
    # Python 2
    from StringIO import StringIO

else:
    # Python 3+
    from io import BytesIO as StringIO

# ------------------------------------------------------------------------------

# Setup the logger
_log = logging.getLogger(__name__)


def log_debug(message, ident=0):
    """
    Logs a message at debug level

    :param message: Message to log
    :param ident: Number of indentation spaces
    """
    _log.debug(" " * (ident * 2) + str(message))


def log_error(message, ident=0):
    """
    Logs a message at error level

    :param message: Message to log
    :param ident: Number of indentation spaces
    """
    _log.error(" " * (ident * 2) + str(message))

# ------------------------------------------------------------------------------

def load(file_object):
    """
    Deserializes Java primitive data and objects serialized using
    ObjectOutputStream from a file-like object.

    :param file_object: A file-like object
    :return: The deserialized object
    """
    marshaller = JavaObjectUnmarshaller(file_object)
    marshaller.add_transformer(DefaultObjectTransformer())
    return marshaller.readObject()


def loads(string):
    """
    Deserializes Java objects and primitive data serialized using
    ObjectOutputStream from a string.

    :param string: A Java data string
    :return: The deserialized object
    """
    f = StringIO(string)
    marshaller = JavaObjectUnmarshaller(f)
    marshaller.add_transformer(DefaultObjectTransformer())
    return marshaller.readObject()


def dumps(obj):
    """
    Serializes Java primitive data and objects unmarshaled by load(s) before
    into string.

    :param obj: A Python primitive object, or one loaded using load(s)
    :return: The serialized data as a string
    """
    marshaller = JavaObjectMarshaller()
    return marshaller.dump(obj)

# ------------------------------------------------------------------------------

class JavaClass(object):
    """
    Represents a class in the Java world
    """
    def __init__(self):
        """
        Sets up members
        """
        self.name = None
        self.serialVersionUID = None
        self.flags = None
        self.fields_names = []
        self.fields_types = []
        self.superclass = None

    def __str__(self):
        """
        String representation of the Java class
        """
        return self.__repr__()

    def __repr__(self):
        """
        String representation of the Java class
        """
        return "[{0:s}:0x{1:X}]".format(self.name, self.serialVersionUID)


class JavaObject(object):
    """
    Represents a deserialized non-primitive Java object
    """
    def __init__(self):
        """
        Sets up members
        """
        self.classdesc = None
        self.annotations = []


    def get_class(self):
        """
        Returns the JavaClass that defines the type of this object
        """
        return self.classdesc


    def __str__(self):
        """
        String representation
        """
        return self.__repr__()


    def __repr__(self):
        """
        String representation
        """
        name = "UNKNOWN"
        if self.classdesc:
            name = self.classdesc.name
        return "<javaobj:{0}>".format(name)


    def copy(self, new_object):
        """
        Returns a shallow copy of this object
        """
        new_object.classdesc = self.classdesc

        for name in self.classdesc.fields_names:
            new_object.__setattr__(name, getattr(self, name))

# ------------------------------------------------------------------------------

class JavaObjectConstants(object):
    """
    Defines the constants of the Java serialization format
    """
    STREAM_MAGIC = 0xaced
    STREAM_VERSION = 0x05

    TC_NULL = 0x70
    TC_REFERENCE = 0x71
    TC_CLASSDESC = 0x72
    TC_OBJECT = 0x73
    TC_STRING = 0x74
    TC_ARRAY = 0x75
    TC_CLASS = 0x76
    TC_BLOCKDATA = 0x77
    TC_ENDBLOCKDATA = 0x78
    TC_RESET = 0x79
    TC_BLOCKDATALONG = 0x7A
    TC_EXCEPTION = 0x7B
    TC_LONGSTRING = 0x7C
    TC_PROXYCLASSDESC = 0x7D
    TC_ENUM = 0x7E
    TC_MAX = 0x7E

    # classDescFlags
    SC_WRITE_METHOD = 0x01  # if SC_SERIALIZABLE
    SC_BLOCK_DATA = 0x08  # if SC_EXTERNALIZABLE
    SC_SERIALIZABLE = 0x02
    SC_EXTERNALIZABLE = 0x04
    SC_ENUM = 0x10

    # type definition chars (typecode)
    TYPE_BYTE = 'B'  # 0x42
    TYPE_CHAR = 'C'
    TYPE_DOUBLE = 'D'  # 0x44
    TYPE_FLOAT = 'F'  # 0x46
    TYPE_INTEGER = 'I'  # 0x49
    TYPE_LONG = 'J'  # 0x4A
    TYPE_SHORT = 'S'  # 0x53
    TYPE_BOOLEAN = 'Z'  # 0x5A
    TYPE_OBJECT = 'L'  # 0x4C
    TYPE_ARRAY = '['  # 0x5B

    # list of supported typecodes listed above
    TYPECODES_LIST = [
            # primitive types
            TYPE_BYTE,
            TYPE_CHAR,
            TYPE_DOUBLE,
            TYPE_FLOAT,
            TYPE_INTEGER,
            TYPE_LONG,
            TYPE_SHORT,
            TYPE_BOOLEAN,
            # object types
            TYPE_OBJECT,
            TYPE_ARRAY ]

    BASE_REFERENCE_IDX = 0x7E0000

# ------------------------------------------------------------------------------

class JavaObjectUnmarshaller(JavaObjectConstants):
    """
    Deserializes a Java serialization stream
    """
    def __init__(self, stream=None):
        """
        Sets up members

        :param stream: An optional input stream
        """
        self.opmap = {
            self.TC_NULL: self.do_null,
            self.TC_CLASSDESC: self.do_classdesc,
            self.TC_OBJECT: self.do_object,
            self.TC_STRING: self.do_string,
            self.TC_ARRAY: self.do_array,
            self.TC_CLASS: self.do_class,
            self.TC_BLOCKDATA: self.do_blockdata,
            self.TC_REFERENCE: self.do_reference,
            self.TC_ENUM: self.do_enum,
            self.TC_ENDBLOCKDATA: self.do_null,  # note that we are reusing of do_null
        }
        self.current_object = None
        self.reference_counter = 0
        self.references = []
        self.object_stream = stream
        self._readStreamHeader()
        self.object_transformers = []


    def readObject(self):
        """
        Reads an object from the input stream
        """
        try:
            opcode, res = self._read_and_exec_opcode(ident=0)  # TODO: add expects

            position_bak = self.object_stream.tell()
            the_rest = self.object_stream.read()
            if len(the_rest):
                log_error("Warning!!!!: Stream still has {0} bytes left. "
                          "Enable debug mode of logging to see the hexdump."\
                          .format(len(the_rest)))
                log_debug(self._create_hexdump(the_rest))
            else:
                log_debug("Java Object unmarshalled successfully!")

            self.object_stream.seek(position_bak)

            return res

        except Exception:
            self._oops_dump_state()
            raise


    def add_transformer(self, transformer):
        """
        Appends an object transformer to the deserialization process

        :param transformer: An object with a transform(obj) method
        """
        self.object_transformers.append(transformer)


    def _readStreamHeader(self):
        """
        Reads the magic header of a Java serialization stream

        :raise IOError: Invalid magic header (not a Java stream)
        """
        (magic, version) = self._readStruct(">HH")
        if magic != self.STREAM_MAGIC or version != self.STREAM_VERSION:
            raise IOError("The stream is not java serialized object. "
                          "Invalid stream header: {0:04X}{1:04X}"\
                          .format(magic, version))


    def _read_and_exec_opcode(self, ident=0, expect=None):
        """
        Reads the next opcode, and executes its handler

        :param ident: Log identation level
        :param expect: A list of expected opcodes
        :return: A tuple: (opcode, result of the handler)
        :raise IOError: Read opcode is not one of the expected ones
        :raise RuntimeError: Unknown opcode
        """
        (opid,) = self._readStruct(">B")
        log_debug("OpCode: 0x{0:X}".format(opid), ident)

        if expect and opid not in expect:
            raise IOError("Unexpected opcode 0x{0:X}".format(opid))

        try:
            handler = self.opmap[opid]
        except KeyError:
            raise RuntimeError("Unknown OpCode in the stream: 0x{0:X}"\
                               .format(opid))
        else:
            return (opid, handler(ident=ident))


    def _readStruct(self, unpack):
        """
        Reads from the input stream, using struct

        :param unpack: An unpack format string
        :return: The result of struct.unpack (tuple)
        :raise RuntimeError: End of stream reached during unpacking
        """
        length = struct.calcsize(unpack)
        ba = self.object_stream.read(length)

        if len(ba) != length:
            raise RuntimeError("Stream has been ended unexpectedly while "
                               "unmarshaling.")

        return struct.unpack(unpack, ba)


    def _readString(self):
        """
        Reads a serialized string

        :return: The deserialized string
        :raise RuntimeError: Unexpected end of stream
        """
        (length,) = self._readStruct(">H")
        ba = self.object_stream.read(length)
        return ba


    def do_classdesc(self, parent=None, ident=0):
        """
        Handles a TC_CLASSDESC opcode

        :param parent:
        :param ident: Log indentation level
        :return: A JavaClass object
        """
        # TC_CLASSDESC className serialVersionUID newHandle classDescInfo
        # classDescInfo:
        #   classDescFlags fields classAnnotation superClassDesc
        # classDescFlags:
        #   (byte)                  // Defined in Terminal Symbols and Constants
        # fields:
        #   (short)<count>  fieldDesc[count]

        # fieldDesc:
        #   primitiveDesc
        #   objectDesc
        # primitiveDesc:
        #   prim_typecode fieldName
        # objectDesc:
        #   obj_typecode fieldName className1
        clazz = JavaClass()
        log_debug("[classdesc]", ident)
        ba = self._readString()
        clazz.name = ba
        log_debug("Class name: %s" % ba, ident)
        (serialVersionUID, newHandle, classDescFlags) = self._readStruct(">LLB")

        # FIXME: Fix for 1.6 ?
        if serialVersionUID == 0:
            serialVersionUID = newHandle

        clazz.serialVersionUID = serialVersionUID
        clazz.flags = classDescFlags

        self._add_reference(clazz)

        log_debug("Serial: 0x%X newHandle: 0x%X. classDescFlags: 0x%X" % (serialVersionUID, newHandle, classDescFlags), ident)
        (length,) = self._readStruct(">H")
        log_debug("Fields num: 0x%X" % length, ident)

        clazz.fields_names = []
        clazz.fields_types = []
        for fieldId in range(length):
            (typecode,) = self._readStruct(">B")
            field_name = self._readString()
            field_type = None
            field_type = self._convert_char_to_type(typecode)

            if field_type == self.TYPE_ARRAY:
                opcode, field_type = self._read_and_exec_opcode(ident=ident + 1, expect=[self.TC_STRING, self.TC_REFERENCE])
                assert type(field_type) is str
#                if field_type is not None:
#                    field_type = "array of " + field_type
#                else:
#                    field_type = "array of None"
            elif field_type == self.TYPE_OBJECT:
                opcode, field_type = self._read_and_exec_opcode(ident=ident + 1, expect=[self.TC_STRING, self.TC_REFERENCE])
                assert type(field_type) is str

            log_debug("FieldName: 0x%X" % typecode + " " + str(field_name) + " " + str(field_type), ident)
            assert field_name is not None
            assert field_type is not None

            clazz.fields_names.append(field_name)
            clazz.fields_types.append(field_type)
        if parent:
            parent.__fields = clazz.fields_names
            parent.__types = clazz.fields_types
        # classAnnotation
        (opid,) = self._readStruct(">B")
        log_debug("OpCode: 0x%X" % opid, ident)
        if opid != self.TC_ENDBLOCKDATA:
            raise NotImplementedError("classAnnotation isn't implemented yet")
        # superClassDesc
        opcode, superclassdesc = self._read_and_exec_opcode(ident=ident + 1, expect=[self.TC_CLASSDESC, self.TC_NULL, self.TC_REFERENCE])
        log_debug(str(superclassdesc), ident)
        clazz.superclass = superclassdesc

        return clazz

    def do_blockdata(self, parent=None, ident=0):
        """
        Handles TC_BLOCKDATA opcode

        :param parent:
        :param ident: Log indentation level
        :return: A string containing the block data
        """
        # TC_BLOCKDATA (unsigned byte)<size> (byte)[size]
        log_debug("[blockdata]", ident)
        (length,) = self._readStruct(">B")
        ba = self.object_stream.read(length)
        return ba


    def do_class(self, parent=None, ident=0):
        """
        Handles TC_CLASS opcode

        :param parent:
        :param ident: Log indentation level
        :return: A JavaClass object
        """
        # TC_CLASS classDesc newHandle
        log_debug("[class]", ident)

        # TODO: what to do with "(ClassDesc)prevObject". (see 3rd line for classDesc:)
        opcode, classdesc = self._read_and_exec_opcode(ident=ident + 1,
                                                expect=(self.TC_CLASSDESC,
                                                        self.TC_PROXYCLASSDESC,
                                                        self.TC_NULL,
                                                        self.TC_REFERENCE))
        log_debug("Classdesc: {0}".format(classdesc), ident)
        self._add_reference(classdesc)
        return classdesc


    def do_object(self, parent=None, ident=0):
        """
        Handles a TC_OBJECT opcode

        :param parent:
        :param ident: Log indentation level
        :return: A JavaClass object
        """
        # TC_OBJECT classDesc newHandle classdata[]  // data for each class
        java_object = JavaObject()
        log_debug("[object]", ident)
        log_debug("java_object.annotations just after instantiation: {0}"\
                  .format(java_object.annotations), ident)

        # TODO: what to do with "(ClassDesc)prevObject". (see 3rd line for classDesc:)
        opcode, classdesc = self._read_and_exec_opcode(ident=ident + 1,
                                               expect=(self.TC_CLASSDESC,
                                                       self.TC_PROXYCLASSDESC,
                                                       self.TC_NULL,
                                                       self.TC_REFERENCE))
        # self.TC_REFERENCE hasn't shown in spec, but actually is here

        self._add_reference(java_object)

        # classdata[]

        # Store classdesc of this object
        java_object.classdesc = classdesc

        if classdesc.flags & self.SC_EXTERNALIZABLE \
        and not classdesc.flags & self.SC_BLOCK_DATA:
            raise NotImplementedError("externalContents isn't implemented yet")  # TODO:

        if classdesc.flags & self.SC_SERIALIZABLE:
            # create megalist
            tempclass = classdesc
            megalist = []
            megatypes = []
            while tempclass:
                log_debug(">>> {0} {1}"\
                          .format(tempclass.fields_names, tempclass), ident)
                log_debug(">>> {0}".format(tempclass.fields_types), ident)

                fieldscopy = tempclass.fields_names[:]
                fieldscopy.extend(megalist)
                megalist = fieldscopy

                fieldscopy = tempclass.fields_types[:]
                fieldscopy.extend(megatypes)
                megatypes = fieldscopy

                tempclass = tempclass.superclass

            log_debug("Values count: {0}".format(len(megalist)), ident)
            log_debug("Prepared list of values: {0}".format(megalist), ident)
            log_debug("Prepared list of types: {0}".format(megatypes), ident)

            for field_name, field_type in zip(megalist, megatypes):
                res = self._read_value(field_type, ident, name=field_name)
                java_object.__setattr__(field_name, res)

        if classdesc.flags & self.SC_SERIALIZABLE \
        and classdesc.flags & self.SC_WRITE_METHOD \
        or classdesc.flags & self.SC_EXTERNALIZABLE \
        and classdesc.flags & self.SC_BLOCK_DATA:
            # objectAnnotation
            log_debug("java_object.annotations before: {0}"\
                      .format(java_object.annotations), ident)

            while opcode != self.TC_ENDBLOCKDATA:
                opcode, obj = self._read_and_exec_opcode(ident=ident + 1)
                # , expect=[self.TC_ENDBLOCKDATA, self.TC_BLOCKDATA,
                # self.TC_OBJECT, self.TC_NULL, self.TC_REFERENCE])
                if opcode != self.TC_ENDBLOCKDATA:
                    java_object.annotations.append(obj)

                log_debug("objectAnnotation value: {0}".format(obj), ident)

            log_debug("java_object.annotations after: {0}" \
                      .format(java_object.annotations), ident)

        # Transform object
        for transformer in self.object_transformers:
            tmp_object = transformer.transform(java_object)
            if tmp_object is not java_object:
                java_object = tmp_object
                break

        log_debug(">>> java_object: {0}".format(java_object), ident)
        return java_object

    def do_string(self, parent=None, ident=0):
        """
        Handles a TC_STRING opcode

        :param parent:
        :param ident: Log indentation level
        :return: A string
        """
        log_debug("[string]", ident)
        ba = self._readString()
        self._add_reference(str(ba))
        return str(ba)

    def do_array(self, parent=None, ident=0):
        """
        Handles a TC_ARRAY opcode

        :param parent:
        :param ident: Log indentation level
        :return: A list of deserialized objects
        """
        # TC_ARRAY classDesc newHandle (int)<size> values[size]
        log_debug("[array]", ident)
        opcode, classdesc = self._read_and_exec_opcode(ident=ident + 1,
                                            expect=(self.TC_CLASSDESC,
                                                    self.TC_PROXYCLASSDESC,
                                                    self.TC_NULL,
                                                    self.TC_REFERENCE))

        array = []

        self._add_reference(array)

        (size,) = self._readStruct(">i")
        log_debug("size: {0}".format(size), ident)

        type_char = classdesc.name[0]
        assert type_char == self.TYPE_ARRAY
        type_char = classdesc.name[1]

        if type_char == self.TYPE_OBJECT or type_char == self.TYPE_ARRAY:
            for i in range(size):
                opcode, res = self._read_and_exec_opcode(ident=ident + 1)
                log_debug("Object value: {0}".format(res), ident)
                array.append(res)
        else:
            for i in range(size):
                res = self._read_value(type_char, ident)
                log_debug("Native value: {0}".format(res), ident)
                array.append(res)

        return array


    def do_reference(self, parent=None, ident=0):
        """
        Handles a TC_REFERENCE opcode

        :param parent:
        :param ident: Log indentation level
        :return:
        """
        (handle,) = self._readStruct(">L")
        log_debug("## Reference handle: 0x{0:X}".format(handle), ident)
        return self.references[handle - self.BASE_REFERENCE_IDX]


    def do_null(self, parent=None, ident=0):
        """
        Handles a TC_NULL opcode

        :param parent:
        :param ident: Log indentation level
        :return: Always None
        """
        return None


    def do_enum(self, parent=None, ident=0):
        """
        Handles a TC_ENUM opcode

        :param parent:
        :param ident: Log indentation level
        :return: An enumeration name
        """
        # TC_ENUM classDesc newHandle enumConstantName
        enum = JavaObject()
        opcode, classdesc = self._read_and_exec_opcode(ident=ident + 1,
                                               expect=(self.TC_CLASSDESC,
                                                       self.TC_PROXYCLASSDESC,
                                                       self.TC_NULL,
                                                       self.TC_REFERENCE))
        self._add_reference(enum)
        opcode, enumConstantName = self._read_and_exec_opcode(ident=ident + 1,
                                                  expect=(self.TC_STRING,
                                                          self.TC_REFERENCE))
        return enumConstantName


    def _create_hexdump(self, src, length=16):
        """
        Prepares an hexadecimal dump string

        :param src: A string containing binary data
        :param length: Length of a dump line
        :return: A dump string
        """
        FILTER = ''.join((len(repr(chr(x))) == 3) and chr(x) or '.'
                         for x in range(256))
        pattern = "{{0:04X}}   {{1:<{0}}}  {{2}}\n".format(length * 3)

        result = []
        for i in range(0, len(src), length):
            s = src[i:i + length]
            hexa = ' '.join("{0:02X}".format(ord(x)) for x in s)
            printable = s.translate(FILTER)
            result.append(pattern.format(i, hexa, printable))

        return ''.join(result)


    def _read_value(self, field_type, ident, name=""):
        """
        Reads the next value, of the given type

        :param field_type: A serialization typecode
        :param ident: Log indentation
        :param name: Field name (for logs)
        :return: The read value
        :raise RuntimeError: Unknown field type
        """
        if len(field_type) > 1:
            # We don't need details for arrays and objects
            field_type = field_type[0]

        if field_type == self.TYPE_BOOLEAN:
            (val,) = self._readStruct(">B")
            res = bool(val)
        elif field_type == self.TYPE_BYTE:
            (res,) = self._readStruct(">b")
        elif field_type == self.TYPE_SHORT:
            (res,) = self._readStruct(">h")
        elif field_type == self.TYPE_INTEGER:
            (res,) = self._readStruct(">i")
        elif field_type == self.TYPE_LONG:
            (res,) = self._readStruct(">q")
        elif field_type == self.TYPE_FLOAT:
            (res,) = self._readStruct(">f")
        elif field_type == self.TYPE_DOUBLE:
            (res,) = self._readStruct(">d")
        elif field_type == self.TYPE_OBJECT or field_type == self.TYPE_ARRAY:
            opcode, res = self._read_and_exec_opcode(ident=ident + 1)
        else:
            raise RuntimeError("Unknown typecode: {0}".format(field_type))

        log_debug("* {0} {1}: {2}".format(field_type, name, res), ident)
        return res

    def _convert_char_to_type(self, type_char):
        """
        Ensures a read character is a typecode.

        :param type_char: Read typecode
        :return: The typecode as a string (using chr)
        :raise RuntimeError: Unknown typecode
        """
        typecode = type_char
        if type(type_char) is int:
            typecode = chr(type_char)

        if typecode in self.TYPECODES_LIST:
            return typecode
        else:
            raise RuntimeError("Typecode {0} ({1}) isn't supported."\
                               .format(type_char, typecode))


    def _add_reference(self, obj):
        """
        Adds a read reference to the marshaler storage
        """
        self.references.append(obj)


    def _oops_dump_state(self):
        """
        Log a deserialization error
        """
        log_error("==Oops state dump" + "=" * (30 - 17))
        log_error("References: {0}".format(self.references))
        log_error("Stream seeking back at -16 byte (2nd line is an actual "
                  "position!):")

        self.object_stream.seek(-16, mode=1)
        the_rest = self.object_stream.read()

        if len(the_rest):
            log_error("Warning!!!!: Stream still has {0} bytes left." \
                      .format(len(the_rest)))
            log_error(self._create_hexdump(the_rest))

        log_error("=" * 30)

# ------------------------------------------------------------------------------

class JavaObjectMarshaller(JavaObjectConstants):
    """
    UNUSABLE: Serializes objects into Java serialization format
    """
    def __init__(self, stream=None):
        """
        Sets up members

        :param stream: An output stream
        """
        self.object_stream = stream


    def dump(self, obj):
        """
        Dumps the given object in the Java serialization format
        """
        self.object_obj = obj
        self.object_stream = StringIO()
        self._writeStreamHeader()
        self.writeObject(obj)
        return self.object_stream.getvalue()


    def _writeStreamHeader(self):
        """
        Writes the Java serialization magic header in the serialization stream
        """
        self._writeStruct(">HH", 4, (self.STREAM_MAGIC, self.STREAM_VERSION))


    def writeObject(self, obj):
        """
        Appends an object to the serialization stream

        :param obj: A string or a deserialized Java object
        :raise RuntimeError: Unsupported type
        """
        log_debug("Writing object of type {0}".format(type(obj).__name__))
        if type(obj) is JavaObject:
            # Deserialized Java object
            self.write_object(obj)
        elif type(obj) is str:
            # String value
            self.write_blockdata(obj)
        else:
            # Unhandled type
            raise RuntimeError("Object serialization of type {0} is not "
                               "supported.".format(type(obj)))


    def _writeStruct(self, unpack, length, args):
        """
        Appends data to the serialization stream

        :param unpack: Struct format string
        :param length: Unused
        :param args: Struct arguments
        """
        ba = struct.pack(unpack, *args)
        self.object_stream.write(ba)


    def _writeString(self, string):
        """
        Appends a string to the serialization stream

        :param string: String to serialize
        """
        self._writeStruct(">H", 2, (len(string),))
        self.object_stream.write(string)


    def write_blockdata(self, obj, parent=None):
        """
        Appends a block of data to the serialization stream

        :param obj: String form of the data block
        """
        # TC_BLOCKDATA (unsigned byte)<size> (byte)[size]
        self._writeStruct(">B", 1, (self.TC_BLOCKDATA,))
        if type(obj) is str:
            self._writeStruct(">B", 1, (len(obj),))
            self.object_stream.write(obj)


    def write_object(self, obj, parent=None):
        """
        Writes an object header to the serialization stream

        :param obj: Not yet used
        :param parent: Not yet used
        """
        self._writeStruct(">B", 1, (self.TC_OBJECT,))
        self._writeStruct(">B", 1, (self.TC_CLASSDESC,))

# ------------------------------------------------------------------------------

class DefaultObjectTransformer(object):
    """
    Default transformer for the deserialized objects.
    Converts JavaObject objects to Python types (maps, lists, ...)
    """
    class JavaList(list, JavaObject):
        pass

    class JavaMap(dict, JavaObject):
        pass

    def transform(self, java_object):
        """
        Transforms a deserialized Java object into a Python object

        :param java_object: A JavaObject instance
        :return: The Python form of the object, or the original JavaObject
        """
        # Get the Java java_object class name
        classname = java_object.get_class().name

        if classname == "java.util.ArrayList":
            # @serialData The length of the array backing the <tt>ArrayList</tt>
            #             instance is emitted (int), followed by all of its
            #             elements (each an <tt>Object</tt>) in the proper order
            log_debug("---")
            log_debug("java.util.ArrayList")
            log_debug(java_object.annotations)
            log_debug("---")

            new_object = self.JavaList()
            java_object.copy(new_object)
            new_object.extend(java_object.annotations[1:])

            log_debug(">>> java_object: {0}".format(new_object))
            return new_object

        elif classname == "java.util.LinkedList":
            log_debug("---")
            log_debug("java.util.LinkedList")
            log_debug(java_object.annotations)
            log_debug("---")

            new_object = self.JavaList()
            java_object.copy(new_object)
            new_object.extend(java_object.annotations[1:])

            log_debug(">>> java_object: {0}".format(new_object))
            return new_object

        elif java_object.get_class().name == "java.util.HashMap":
            log_debug("---")
            log_debug("java.util.HashMap")
            log_debug(java_object.annotations)
            log_debug("---")

            new_object = self.JavaMap()
            java_object.copy(new_object)

            for i in range((len(java_object.annotations) - 1) / 2):
                new_object[java_object.annotations[i * 2 + 1]] = \
                                                java_object.annotations[i * 2 + 2]

            log_debug(">>> java_object: {0}".format(new_object))
            return new_object

        else:
            # Return the JavaObject by default
            return java_object
