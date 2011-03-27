import StringIO
import struct

def loads(object):
    """
    Deserializes Java primitive data and objects serialized by ObjectOutputStream
    from a string.
    See: http://download.oracle.com/javase/6/docs/platform/serialization/spec/protocol.html
    """
    f = StringIO.StringIO(object)
    marshaller = JavaObjectMarshaller()
    return marshaller.load_stream(f)

def dumps(object):
    """
    Serializes Java primitive data and objects unmarshaled by load(s) before into string.
    """
    marshaller = JavaObjectMarshaller()
    return marshaller.dump(object)


class JavaClass(object):
    def __init__(self):
        self.name = None
        self.serialVersionUID = None
        self.flags = None
        self.fields_names = []
        self.fields_types = []
        self.superclass = None

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "[%s:0x%X]" % (self.name, self.serialVersionUID)


class JavaObject(object):
    classdesc = None

    def get_class(self):
        return self.classdesc


class JavaObjectMarshaller:

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
    SC_WRITE_METHOD = 0x01 # if SC_SERIALIZABLE
    SC_BLOCK_DATA = 0x08   # if SC_EXTERNALIZABLE
    SC_SERIALIZABLE = 0x02
    SC_EXTERNALIZABLE = 0x04
    SC_ENUM = 0x10

    # type definition chars (typecode)
    TYPE_BYTE = 'B'     # 0x42
    TYPE_CHAR = 'C'
    TYPE_DOUBLE = 'D'   # 0x44
    TYPE_FLOAT = 'F'    # 0x46
    TYPE_INTEGER = 'I'  # 0x49
    TYPE_LONG = 'J'     # 0x4A
    TYPE_SHORT = 'S'    # 0x53
    TYPE_BOOLEAN = 'Z'  # 0x5A
    TYPE_OBJECT = 'L'   # 0x4C
    TYPE_ARRAY = '['    # 0x5B

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

    def __init__(self):
        self.opmap = {
            self.TC_NULL: self.do_null,
            self.TC_CLASSDESC: self.do_classdesc,
            self.TC_OBJECT: self.do_object,
            self.TC_STRING: self.do_string,
            self.TC_ARRAY: self.do_array,
            self.TC_CLASS: self.do_class,
            self.TC_BLOCKDATA: self.do_blockdata,
            self.TC_REFERENCE: self.do_reference
        }
        self.current_object = None
        self.reference_counter = 0
        self.references = []

    def load_stream(self, stream):
        try:
            self.object_stream = stream
            self._readStreamHeader()
            return self.readObject()
        except Exception, e:
            self._oops_dump_state()
            raise

    def _readStreamHeader(self):
        (magic, version) = self._readStruct(">HH")
        if magic != self.STREAM_MAGIC or version != self.STREAM_VERSION:
            raise IOError("The stream is not java serialized object. Invalid stream header: %04X%04X" % (magic, version))

    def readObject(self):
        res = self._read_and_exec_opcode(ident=0)    # TODO: add expects

        the_rest = self.object_stream.read()
        if len(the_rest):
            print "Warning!!!!: Stream still has %s bytes left." % len(the_rest)
            print self._create_hexdump(the_rest)
        else:
            print "Ok!!!!"

        return res

    def _read_and_exec_opcode(self, ident=0, expect=None):
        (opid, ) = self._readStruct(">B")
        self._log_ident("OpCode: 0x%X" % opid, ident)
        if expect and opid not in expect:
            raise IOError("Unexpected opcode 0x%X" % opid)
        return self.opmap.get(opid, self.do_unknown)(ident=ident)

    def _readStruct(self, unpack):
        length = struct.calcsize(unpack)
        ba = self.object_stream.read(length)
        return struct.unpack(unpack, ba)

    def _readString(self):
        (length, ) = self._readStruct(">H")
        ba = self.object_stream.read(length)
        return ba

    def do_classdesc(self, parent=None, ident=0):
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
        self._log_ident("[classdesc]", ident)
        ba = self._readString()
        clazz.name = ba
        self._log_ident("Class name: %s" % ba, ident)
        (serialVersionUID, newHandle, classDescFlags) = self._readStruct(">LLB")
        clazz.serialVersionUID = serialVersionUID
        clazz.flags = classDescFlags

        self._add_reference(clazz)

        self._log_ident("Serial: 0x%X newHandle: 0x%X. classDescFlags: 0x%X" % (serialVersionUID, newHandle, classDescFlags), ident)
        (length, ) = self._readStruct(">H")
        self._log_ident("Fields num: 0x%X" % length, ident)

        clazz.fields_names = []
        clazz.fields_types = []
        for fieldId in range(length):
            (type, ) = self._readStruct(">B")
            field_name = self._readString()
            field_type = None
            field_type = self._convert_char_to_type(type)

            if field_type == self.TYPE_ARRAY:
                field_type = self._read_and_exec_opcode(ident=ident+1, expect=[self.TC_STRING, self.TC_REFERENCE])
#                if field_type is not None:
#                    field_type = "array of " + field_type
#                else:
#                    field_type = "array of None"
            elif field_type == self.TYPE_OBJECT:
                field_type = self._read_and_exec_opcode(ident=ident+1, expect=[self.TC_STRING, self.TC_REFERENCE])

            self._log_ident("FieldName: 0x%X" % type + " " + str(field_name) + " " + str(field_type), ident)
            assert field_name is not None
            assert field_type is not None

            clazz.fields_names.append(field_name)
            clazz.fields_types.append(field_type)
        if parent:
            parent.__fields = clazz.fields_names
            parent.__types = clazz.fields_types
        # classAnnotation
        (opid, ) = self._readStruct(">B")
        if opid != self.TC_ENDBLOCKDATA:
            raise NotImplementedError("classAnnotation isn't implemented yet")
        self._log_ident("OpCode: 0x%X" % opid, ident)
        # superClassDesc
        superclassdesc = self._read_and_exec_opcode(ident=ident+1, expect=[self.TC_CLASSDESC, self.TC_NULL, self.TC_REFERENCE])
        self._log_ident(str(superclassdesc), ident)
        clazz.superclass = superclassdesc

        return clazz

    def do_blockdata(self, parent=None, ident=0):
        # TC_BLOCKDATA (unsigned byte)<size> (byte)[size]
        self._log_ident("[blockdata]", ident)
        (length, ) = self._readStruct(">B")
        ba = self.object_stream.read(length)
        return ba

    def do_class(self, parent=None, ident=0):
        # TC_CLASS classDesc newHandle
        self._log_ident("[class]", ident)

        # TODO: what to do with "(ClassDesc)prevObject". (see 3rd line for classDesc:)
        classdesc = self._read_and_exec_opcode(ident=ident+1, expect=[self.TC_CLASSDESC, self.TC_PROXYCLASSDESC, self.TC_NULL, self.TC_REFERENCE])
        self._log_ident("Classdesc: %s" % classdesc, ident)
        self._add_reference(classdesc)
        return classdesc

    def do_object(self, parent=None, ident=0):
        # TC_OBJECT classDesc newHandle classdata[]  // data for each class
        java_object = JavaObject()
        self._log_ident("[object]", ident)

        # TODO: what to do with "(ClassDesc)prevObject". (see 3rd line for classDesc:)
        classdesc = self._read_and_exec_opcode(ident=ident+1, expect=[self.TC_CLASSDESC, self.TC_PROXYCLASSDESC, self.TC_NULL, self.TC_REFERENCE])
        # self.TC_REFERENCE hasn't shown in spec, but actually is here

        self._add_reference(java_object)

        # classdata[]

        # Store classdesc of this object
        java_object.classdesc = classdesc

        if classdesc.flags & self.SC_EXTERNALIZABLE and not classdesc.flags & self.SC_BLOCK_DATA:
            raise NotImplementedError("externalContents isn't implemented yet") # TODO:

        if classdesc.flags & self.SC_SERIALIZABLE:
            # create megalist
            tempclass = classdesc
            megalist = []
            megatypes = []
            while tempclass:
                self._log_ident(">>> " + str(tempclass.fields_names) + " " + str(tempclass), ident)
                fieldscopy = tempclass.fields_names[:]
                fieldscopy.extend(megalist)
                megalist = fieldscopy

                fieldscopy = tempclass.fields_types[:]
                fieldscopy.extend(megatypes)
                megatypes = fieldscopy

                tempclass = tempclass.superclass

            self._log_ident("Values count: %s" % str(len(megalist)), ident)
            self._log_ident("Prepared list of values: %s" % str(megalist), ident)
            self._log_ident("Prepared list of types: %s" % str(megatypes), ident)

            for field_name, field_type in zip(megalist, megatypes):
                res = self._read_value(field_type, ident, name=field_name)
                java_object.__setattr__(field_name, res)

        if classdesc.flags & self.SC_SERIALIZABLE and classdesc.flags & self.SC_WRITE_METHOD or classdesc.flags & self.SC_EXTERNALIZABLE and classdesc.flags & self.SC_BLOCK_DATA:
            # objectAnnotation
            (opid, ) = self._readStruct(">B")
            if opid != self.TC_ENDBLOCKDATA: # 0x78:
                self.object_stream.seek(-1, mode=1)
                print self._create_hexdump(self.object_stream.read())
                raise NotImplementedError("objectAnnotation isn't fully implemented yet") # TODO:


        return java_object

    def do_string(self, parent=None, ident=0):
        self._log_ident("[string]", ident)
        ba = self._readString()
        self._add_reference(str(ba))
        return str(ba)

    def do_array(self, parent=None, ident=0):
        # TC_ARRAY classDesc newHandle (int)<size> values[size]
        self._log_ident("[array]", ident)
        classdesc = self._read_and_exec_opcode(ident=ident+1, expect=[self.TC_CLASSDESC, self.TC_PROXYCLASSDESC, self.TC_NULL, self.TC_REFERENCE])

        array = []

        self._add_reference(array)

        (size, ) = self._readStruct(">i")
        self._log_ident("size: " + str(size), ident)

        type_char = classdesc.name[0]
        assert type_char == self.TYPE_ARRAY
        type_char = classdesc.name[1]

        if type_char == self.TYPE_OBJECT or type_char == self.TYPE_ARRAY:
            for i in range(size):
                res = self._read_and_exec_opcode(ident=ident+1)
                self._log_ident("Object value: %s" % str(res), ident)
                array.append(res)
        else:
            for i in range(size):
                res = self._read_value(type_char, ident)
                self._log_ident("Native value: %s" % str(res), ident)
                array.append(res)

        return array

    def do_reference(self, parent=None, ident=0):
        (handle, ) = self._readStruct(">L")
        self._log_ident("## Reference handle: 0x%x" % (handle), ident)
        return self.references[handle - self.BASE_REFERENCE_IDX]

    def do_null(self, parent=None, ident=0):
        return None

    def do_unknown(self, parent=None, ident=0):
        raise RuntimeError("Unknown OpCode")

    def _log_ident(self, message, ident):
        print " " * (ident * 2) + str(message)

    def _create_hexdump(self, src, length=16):
        FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])
        result = []
        for i in xrange(0, len(src), length):
            s = src[i:i+length]
            hexa = ' '.join(["%02X"%ord(x) for x in s])
            printable = s.translate(FILTER)
            result.append("%04X   %-*s  %s\n" % (i, length*3, hexa, printable))
        return ''.join(result)

    def _read_value(self, field_type, ident, name = ""):
        if len(field_type) > 1:
            field_type = field_type[0]  # We don't need details for arrays and objects

        if field_type == self.TYPE_BOOLEAN:
            (val, ) = self._readStruct(">B")
            res = bool(val)
        elif field_type == self.TYPE_BYTE:
            (res, ) = self._readStruct(">b")
        elif field_type == self.TYPE_SHORT:
            (res, ) = self._readStruct(">h")
        elif field_type == self.TYPE_INTEGER:
            (res, ) = self._readStruct(">i")
        elif field_type == self.TYPE_LONG:
            (res, ) = self._readStruct(">q")
        elif field_type == self.TYPE_FLOAT:
            (res, ) = self._readStruct(">f")
        elif field_type == self.TYPE_DOUBLE:
            (res, ) = self._readStruct(">d")
        elif field_type == self.TYPE_OBJECT or field_type == self.TYPE_ARRAY:
            res = self._read_and_exec_opcode(ident=ident+1)
        else:
            raise RuntimeError("Unknown typecode: %s" % field_type)
        self._log_ident("* %s %s: " % (field_type, name) + str(res), ident)
        return res

    def _convert_char_to_type(self, type_char):
        typecode = type_char
        if type(type_char) is int:
            typecode = chr(type_char)

        if typecode in self.TYPECODES_LIST:
            return typecode
        else:
            raise RuntimeError("Typecode %s (%s) isn't supported." % (type_char, typecode))

    def _add_reference(self, obj):
        self.references.append(obj)

    def _oops_dump_state(self):
        print "==Oops state dump" + "=" * (30 - 17)
        print "References:", self.references
        print "Stream seeking back at -16 byte (2nd line is an actual position!):"
        self.object_stream.seek(-16, mode=1)
        the_rest = self.object_stream.read()
        if len(the_rest):
            print "Warning!!!!: Stream still has %s bytes left." % len(the_rest)
            print self._create_hexdump(the_rest)
        print "=" * 30
    # =====================================================================================

    def dump(self, obj):
        self.object_obj = obj
        self.object_stream = StringIO.StringIO()
        self._writeStreamHeader()
        self.writeObject(obj)
        return self.object_stream.getvalue()

    def _writeStreamHeader(self):
        self._writeStruct(">HH", 4, (self.STREAM_MAGIC, self.STREAM_VERSION))

    def writeObject(self, obj):
        print type(obj)
        print obj
        if type(obj) is JavaObject:
            print "This is java object!"
            self.write_object(obj)
        elif type(obj) is str:
            print "This is string."
            self.write_blockdata(obj)
#        (opid, ) = self._readStruct(">B")
#        print "OpCode: 0x%X" % opid
#        res = self.opmap.get(opid, self.do_default_stuff)()
#        return res

    def _writeStruct(self, unpack, length, args):
        ba = struct.pack(unpack, *args)
        self.object_stream.write(ba)

    def _writeString(self, string):
        len = len(string)
        self._writeStruct(">H", 2, (len, ))
        self.object_stream.write(string)

    def write_blockdata(self, obj, parent=None):
        self._writeStruct(">B", 1, (self.TC_BLOCKDATA, ))
        # TC_BLOCKDATA (unsigned byte)<size> (byte)[size]
        if type(obj) is str:
            print "This is string."
            self._writeStruct(">B", 1, (len(obj), ))
            self.object_stream.write(obj)

    def write_object(self, obj, parent=None):
        # TC_OBJECT classDesc newHandle classdata[]  // data for each class
#        self.current_object = JavaObject()
#        print "[object]"
        self._writeStruct(">B", 1, (self.TC_OBJECT, ))
        self._writeStruct(">B", 1, (self.TC_CLASSDESC, ))

#        print "OpCode: 0x%X" % opid
#        classdesc = self.opmap.get(opid, self.do_default_stuff)(self.current_object)
#        self.finalValue = classdesc
#        # classdata[]
#
#        # Store classdesc of this object
#        self.current_object.classdesc = classdesc
#
#        for field_name in self.current_object.__fields:
#            (opid, ) = self._readStruct(">B")
#            print "OpCode: 0x%X" % opid
#            res = self.opmap.get(opid, self.do_default_stuff)(self.current_object)
#            self.current_object.__setattr__(field_name, res)
#        return self.current_object
