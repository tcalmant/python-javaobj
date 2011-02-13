import StringIO
import struct

def loads(object):
    f = StringIO.StringIO(object)
    ba = f.read(4)
    (magic, version) = struct.unpack(">HH", ba)
    print magic
    if magic != 0xaced:
        raise RuntimeError("The stream is not java serialized object. Magic number failed.")

    print version

    print type(object), Magic
  