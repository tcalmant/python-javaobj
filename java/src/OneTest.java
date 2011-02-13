import java.io.ByteArrayOutputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.util.Hashtable;
import java.util.Vector;

import org.junit.Before;
import org.junit.Test;

public class OneTest {

	ObjectOutputStream oos;
	ByteArrayOutputStream bao;
	FileOutputStream fos;
	static int counter;

	public class SerializableTestHelper implements Serializable {

		public String aField1;

		public String aField2;

		SerializableTestHelper() {
			aField1 = null;
			aField2 = null;
		}

		SerializableTestHelper(String s, String t) {
			aField1 = s;
			aField2 = t;
		}

		private void readObject(ObjectInputStream ois) throws Exception {
			// note aField2 is not read
			ObjectInputStream.GetField fields = ois.readFields();
			aField1 = (String) fields.get("aField1", "Zap");
		}

		private void writeObject(ObjectOutputStream oos) throws IOException {
			// note aField2 is not written
			ObjectOutputStream.PutField fields = oos.putFields();
			fields.put("aField1", aField1);
			oos.writeFields();
		}

		public String getText1() {
			return aField1;
		}

		public void setText1(String s) {
			aField1 = s;
		}

		public String getText2() {
			return aField2;
		}

		public void setText2(String s) {
			aField2 = s;
		}
	}

	public static class A1 implements Serializable {
		private static final long serialVersionUID = 5942584913446079661L;
		B1 b1 = new B1();
		B1 b2 = b1;
		Vector v = new Vector();
	}

	public static class B1 implements Serializable {
		int i = 5;
		Hashtable h = new Hashtable();
	}

	@Before
	public void setUp() throws Exception {
		oos = new ObjectOutputStream(fos = new FileOutputStream("obj" + counter++
				+ ".ser"));
	}

	@Test
	public void testDouble() throws IOException {
		oos.writeDouble(Double.MAX_VALUE);
		oos.close();
	}

	@Test
	public void testBytes() throws IOException {
		oos.writeBytes("HelloWorld");
		oos.close();
	}

	@Test
	public void testBoolean() throws IOException {
		oos.writeBoolean(false);
		oos.close();
	}

	@Test
	public void testByte() throws IOException {
		oos.writeByte(127);
		oos.close();
	}

	@Test
	public void testChar() throws IOException {
		oos.writeChar('C');
		oos.close();
	}
	
	@Test
    public void test_readFields() throws Exception {
        oos.writeObject(new SerializableTestHelper("Gabba", "Jabba"));
        oos.flush();
    }

	@Test
    public void testClass() throws Exception {
        oos.writeObject(String.class);
        oos.flush();
    }
	
//    public void test_readObject() throws Exception {
//        String s = "HelloWorld";
//        oos.writeObject(s);
//        oos.close();
//        ois = new ObjectInputStream(new ByteArrayInputStream(bao.toByteArray()));
//        assertEquals("Read incorrect Object value", s, ois.readObject());
//        ois.close();
//
//        // Regression for HARMONY-91
//        // dynamically create serialization byte array for the next hierarchy:
//        // - class A implements Serializable
//        // - class C extends A
//
//        byte[] cName = C.class.getName().getBytes("UTF-8");
//        byte[] aName = A.class.getName().getBytes("UTF-8");
//
//        ByteArrayOutputStream out = new ByteArrayOutputStream();
//
//        byte[] begStream = new byte[] { (byte) 0xac, (byte) 0xed, // STREAM_MAGIC
//                (byte) 0x00, (byte) 0x05, // STREAM_VERSION
//                (byte) 0x73, // TC_OBJECT
//                (byte) 0x72, // TC_CLASSDESC
//                (byte) 0x00, // only first byte for C class name length
//        };
//
//        out.write(begStream, 0, begStream.length);
//        out.write(cName.length); // second byte for C class name length
//        out.write(cName, 0, cName.length); // C class name
//
//        byte[] midStream = new byte[] { (byte) 0x00, (byte) 0x00, (byte) 0x00,
//                (byte) 0x00, (byte) 0x00, (byte) 0x00, (byte) 0x00,
//                (byte) 0x21, // serialVersionUID = 33L
//                (byte) 0x02, // flags
//                (byte) 0x00, (byte) 0x00, // fields : none
//                (byte) 0x78, // TC_ENDBLOCKDATA
//                (byte) 0x72, // Super class for C: TC_CLASSDESC for A class
//                (byte) 0x00, // only first byte for A class name length
//        };
//
//        out.write(midStream, 0, midStream.length);
//        out.write(aName.length); // second byte for A class name length
//        out.write(aName, 0, aName.length); // A class name
//
//        byte[] endStream = new byte[] { (byte) 0x00, (byte) 0x00, (byte) 0x00,
//                (byte) 0x00, (byte) 0x00, (byte) 0x00, (byte) 0x00,
//                (byte) 0x0b, // serialVersionUID = 11L
//                (byte) 0x02, // flags
//                (byte) 0x00, (byte) 0x01, // fields
//
//                (byte) 0x4c, // field description: type L (object)
//                (byte) 0x00, (byte) 0x04, // length
//                // field = 'name'
//                (byte) 0x6e, (byte) 0x61, (byte) 0x6d, (byte) 0x65,
//
//                (byte) 0x74, // className1: TC_STRING
//                (byte) 0x00, (byte) 0x12, // length
//                //
//                (byte) 0x4c, (byte) 0x6a, (byte) 0x61, (byte) 0x76,
//                (byte) 0x61, (byte) 0x2f, (byte) 0x6c, (byte) 0x61,
//                (byte) 0x6e, (byte) 0x67, (byte) 0x2f, (byte) 0x53,
//                (byte) 0x74, (byte) 0x72, (byte) 0x69, (byte) 0x6e,
//                (byte) 0x67, (byte) 0x3b,
//
//                (byte) 0x78, // TC_ENDBLOCKDATA
//                (byte) 0x70, // NULL super class for A class
//
//                // classdata
//                (byte) 0x74, // TC_STRING
//                (byte) 0x00, (byte) 0x04, // length
//                (byte) 0x6e, (byte) 0x61, (byte) 0x6d, (byte) 0x65, // value
//        };
//
//        out.write(endStream, 0, endStream.length);
//        out.flush();
//
//        // read created serial. form
//        ObjectInputStream ois = new ObjectInputStream(new ByteArrayInputStream(
//                out.toByteArray()));
//        Object o = ois.readObject();
//        assertEquals(C.class, o.getClass());
//
//                // Regression for HARMONY-846
//        assertNull(new ObjectInputStream() {}.readObject());
//    }


}
