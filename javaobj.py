import StringIO
import struct

def loads(object):
    """
    Deserializes Java primitive data and objects serialized by ObjectOutputStream
    """
    f = StringIO.StringIO(object)
    marshaller = JavaObjectMarshaller(f)
    return marshaller.readObject()
#    ba = f.read(4)
#    (magic, version) = struct.unpack(">HH", ba)
#    print magic
#    if magic != 0xaced:
#        raise RuntimeError("The stream is not java serialized object. Magic number failed.")
#
#    print version
#
#    print type(object), Magic

class JavaObjectMarshaller:

    STREAM_MAGIC = 0xaced
    STREAM_VERSION = 0x05

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

    def __init__(self, stream):
        self.opmap = {
           self.TC_CLASSDESC: self.do_classdesc,
           self.TC_OBJECT: self.do_object,
           self.TC_STRING: self.do_string,
           self.TC_CLASS: self.do_class,
           self.TC_BLOCKDATA: self.do_blockdata,
           self.TC_REFERENCE: self.do_reference
        }
        self.object_stream = stream
        self._readStreamHeader()
        self.finalValue = True

    def _readStreamHeader(self):
        (magic, version) = self._readStruct(">HH", 4)
        if magic != self.STREAM_MAGIC or version != self.STREAM_VERSION:
            raise IOError("The stream is not java serialized object. Invalid stream header: %04X%04X" % (magic, version))

    def readObject(self):
        (opid, ) = self._readStruct(">B", 1)
        print "OpCode: 0x%X" % opid
        self.opmap.get(opid, self.do_default_stuff)()
        return self.finalValue

    def _readStruct(self, unpack, length):
        ba = self.object_stream.read(length)
        return struct.unpack(unpack, ba)

    def _readString(self):
        (length, ) = self._readStruct(">H", 2)
        ba = self.object_stream.read(length)
        return ba

    def do_classdesc(self):
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
        print "do_classdesc"
        ba = self._readString()
        print "Class name:", ba
        (serialVersionUID, newHandle, classDescFlags) = self._readStruct(">LLB", 4+4+1)
        print "Serial: 0x%X newHanle: 0x%X. classDescFlags: 0x%X" % (serialVersionUID, newHandle, classDescFlags)
        (length, ) = self._readStruct(">H", 2)
        print "Fields num: 0x%X" % length

        for fieldId in range(length):
            (type, ) = self._readStruct(">B", 1)
            ba = self._readString()
            print "FieldType: 0x%X" % type, ba
            (opid, ) = self._readStruct(">B", 1)
            print "OpCode: 0x%X" % opid
            res = self.opmap.get(opid, self.do_default_stuff)()

    def do_blockdata(self):
        # TC_BLOCKDATA (unsigned byte)<size> (byte)[size]
        print "[blockdata]"
        (length, ) = self._readStruct(">B", 1)
        ba = self.object_stream.read(length)
        self.finalValue = ba

    def do_class(self):
        # TC_CLASS classDesc newHandle
        print "[class]"

    def do_object(self):
        # TC_OBJECT classDesc newHandle classdata[]  // data for each class
        print "[object]"
        (opid, ) = self._readStruct(">B", 1)
        print "OpCode: 0x%X" % opid
        res = self.opmap.get(opid, self.do_default_stuff)()
        self.finalValue = res

    def do_string(self):
        print "[string]"
        ba = self._readString()
#        (handle, ) = self._readStruct(">B", 1)
        return str(ba)

    def do_reference(self):
        (handle, reference) = self._readStruct(">HH", 4)
        pass

    def do_default_stuff(self):
        raise RuntimeError("Unknown opcode")
