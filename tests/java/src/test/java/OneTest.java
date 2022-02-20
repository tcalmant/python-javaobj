import java.awt.event.WindowAdapter;
import java.awt.event.WindowEvent;
import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Hashtable;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.Vector;
import java.util.Random;
import java.util.zip.GZIPOutputStream;

import javax.swing.JScrollPane;
import javax.swing.SwingUtilities;

import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TestName;

class ClassWithEnum implements Serializable {
	/**
	 *
	 */
	private static final long serialVersionUID = 1L;
	public Color color = Color.GREEN;
	public Color[] colors = { Color.GREEN, Color.BLUE, Color.RED };
}

class ClassWithByteArray implements Serializable {
	private static final long serialVersionUID = 1L;
	public byte[] myArray = new byte[]{1,3,7,11};
}

enum Color {
	BLUE("BLUE"), GREEN("GREEN"), RED("RED"), UNKNOWN("UNKNOWN");
	private final String value;

	Color(final String value) {
		this.value = value;
	}

	public String getValue() {
		return value;
	}
}

class MyExceptionWhenDumping implements java.io.Serializable {
	protected static class MyException extends java.io.IOException {

		/**
		 *
		 */
		private static final long serialVersionUID = 1L;
	}

	/**
	 *
	 */
	private static final long serialVersionUID = 1L;;

	public boolean anInstanceVar = false;

	public MyExceptionWhenDumping() {
		super();
	}

	private void readObject(final java.io.ObjectInputStream in)
			throws java.io.IOException, ClassNotFoundException {
		in.defaultReadObject();
	}

	private void writeObject(final java.io.ObjectOutputStream out)
			throws java.io.IOException, ClassNotFoundException {
		throw new MyException();
	}
}

public class OneTest {

	public static class A1 implements Serializable {
		private static final long serialVersionUID = 5942584913446079661L;
		B1 b1 = new B1();
		B1 b2 = b1;
		Vector<Object> v = new Vector<Object>();
	}

	public static class B1 implements Serializable {
		/**
		 *
		 */
		private static final long serialVersionUID = 1L;
		Hashtable<Object, Object> h = new Hashtable<Object, Object>();
		int i = 5;
	}

	public class SerializableTestHelper implements Serializable {

		/**
		 *
		 */
		private static final long serialVersionUID = 0x7F0941F5L;

		public String aField1;

		public String aField2;

		SerializableTestHelper() {
			aField1 = null;
			aField2 = null;
		}

		SerializableTestHelper(final String s, final String t) {
			aField1 = s;
			aField2 = t;
		}

		public String getText1() {
			return aField1;
		}

		public String getText2() {
			return aField2;
		}

		private void readObject(final ObjectInputStream ois) throws Exception {
			// note aField2 is not read
			final ObjectInputStream.GetField fields = ois.readFields();
			aField1 = (String) fields.get("aField1", "Zap");
		}

		public void setText1(final String s) {
			aField1 = s;
		}

		public void setText2(final String s) {
			aField2 = s;
		}

		private void writeObject(final ObjectOutputStream oos)
				throws IOException {
			// note aField2 is not written
			final ObjectOutputStream.PutField fields = oos.putFields();
			fields.put("aField1", aField1);
			oos.writeFields();
		}
	}

	ByteArrayOutputStream bao;

	FileOutputStream fos;

	@Rule
	public TestName name = new TestName();

	ObjectOutputStream oos;

    /**
     * Returns the name of the file where to serialize the test content
     */
    private String getTestFileName() {
        return name.getMethodName() + ".ser";
    }

	@Before
	public void setUp() throws Exception {
		oos = new ObjectOutputStream(fos = new FileOutputStream(getTestFileName()));
	}

	@Test
	public void test_readFields() throws Exception {
		oos.writeObject(new SerializableTestHelper("Gabba", "Jabba"));
		oos.flush();
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
	public void testBytes() throws IOException {
		oos.writeBytes("HelloWorld");
		oos.close();
	}

	@Test
	public void testChar() throws IOException {
		oos.writeChar('C');
		oos.close();
	}

	@Test
	public void testChars() throws IOException {
		oos.writeChars("python-javaobj");
		oos.close();

        // Also compress the file
        final String serializedFileName = getTestFileName();
        final String gzippedFileName = serializedFileName + ".gz";

        try (final GZIPOutputStream out = new GZIPOutputStream(new FileOutputStream(gzippedFileName))){
            try (final FileInputStream in = new FileInputStream(serializedFileName)){
                final byte[] buffer = new byte[1024];
                int len;
                while((len = in.read(buffer)) != -1){
                    out.write(buffer, 0, len);
                }
            }
        }
	}

	@Test
	public void testCharArray() throws IOException {
		char[] array = new char[] {
			'\u0000', '\ud800',
			'\u0001', '\udc00',
			'\u0002', '\uffff',
			'\u0003'
		};
		oos.writeObject(array);
		oos.close();
	}

	@Test
	public void test2DArray() throws IOException {
		int[][] array = new int[][] {
			new int[] {1, 2, 3},
			new int[] {4, 5, 6},
		};
		oos.writeObject(array);
		oos.close();
	}

	@Test
	public void testClassArray() throws IOException {
		Class<?>[] array = new Class<?>[] {
			Integer.class,
			ObjectOutputStream.class,
			Exception.class,
		};
		oos.writeObject(array);
		oos.close();
	}

	@Test
	public void testJapan() throws IOException {
		String stateOfJapan = "日本国";
		oos.writeObject(stateOfJapan);
		oos.close();
	}

	@Test
	public void testClass() throws Exception {
		oos.writeObject(String.class);
		oos.flush();
	}

	@Test
	public void testDouble() throws IOException {
		oos.writeDouble(Double.MAX_VALUE);
		oos.close();
	}

	@Test
	public void testEnums() throws Exception {
		oos = new ObjectOutputStream(fos = new FileOutputStream("objEnums.ser"));
		final ClassWithEnum ts = new ClassWithEnum();

		oos.writeObject(ts);
		oos.flush();
	}

	@Test
	public void testException() throws Exception {
		oos = new ObjectOutputStream(fos = new FileOutputStream(
				"objException.ser"));
		final MyExceptionWhenDumping ts = new MyExceptionWhenDumping();

		try {
			oos.writeObject(ts);
			oos.flush();
		} catch (final MyExceptionWhenDumping.MyException ex) {
			// Was intended
			return;
		}
	}

	@Test
	public void testClassWithByteArray() throws Exception {
		final ClassWithByteArray cwba = new ClassWithByteArray();
		oos.writeObject(cwba);
		oos.flush();
	}

	@Test
	public void testSuper() throws Exception {
		oos = new ObjectOutputStream(fos = new FileOutputStream("objSuper.ser"));
		final TestConcrete ts = new TestConcrete();

		// ts.setChild("and Child!!!!");
		oos.writeObject(ts);
		oos.flush();
	}

	@Test
	public void testHashSet() throws Exception {
		final Set<Integer> set = new HashSet<Integer>();
		set.add(1);
		set.add(2);
		set.add(1);
		set.add(42);
		oos.writeObject(set);
		oos.flush();
	}

	@Test
	public void testLinkedHashSet() throws Exception {
		final Set<Integer> set = new LinkedHashSet<Integer>();
		set.add(1);
		set.add(2);
		set.add(1);
		set.add(42);
		oos.writeObject(set);
		oos.flush();
	}

	@Test
	public void testTreeSet() throws Exception {
		final Set<Integer> set = new TreeSet<Integer>();
		set.add(1);
		set.add(2);
		set.add(1);
		set.add(42);
		oos.writeObject(set);
		oos.flush();
    }

    @Test
    public void testTime() throws Exception {
        oos.writeObject(new Object[] {
            Duration.ofSeconds(10),
            Instant.now(),
            LocalDate.now(),
            LocalTime.now(),
            LocalDateTime.now(),
            ZoneId.systemDefault(),
            ZonedDateTime.now(),
        });
        oos.flush();
	}

    /**
     * Tests th pull request #27 by @qistoph:
     * Add support for java.lang.Bool, Integer and Long classes
     */
    @Test
    public void testBoolIntLong() throws Exception {
        Map<String, Object> hm1 = new HashMap<String, Object>();
        hm1.put("key1", "value1");
        hm1.put("key2", "value2");
        hm1.put("int", 9);
        hm1.put("int2", new Integer(10));
        hm1.put("bool", true);
        hm1.put("bool2", new Boolean(true));

        oos.writeObject(hm1);
		oos.flush();

        Map<String, Object> hm2 = new HashMap<String, Object>();
        hm2.put("subMap", hm1);

        ObjectOutputStream oos2 = new ObjectOutputStream(new FileOutputStream(name.getMethodName() + "-2.ser"));
        try {
            oos2.writeObject(hm2);
        } finally {
            oos2.close();
        }
    }

	@Test
	public void testSwingObject() throws Exception {

		// Start the frame in the UI thread
		SwingUtilities.invokeAndWait(new Runnable() {

			@Override
			public void run() {

				final JFrameTest frame = new JFrameTest();
				frame.addWindowListener(new WindowAdapter() {
					@Override
					public void windowClosing(final WindowEvent e) {
						System.exit(0);
					}
				});
				frame.setSize(300, 200);
				frame.setVisible(true);

				try {
					oos.writeObject(((JScrollPane) frame.getRootPane()
							.getContentPane().getComponent(0)).getComponent(1));
					oos.flush();

				} catch (final IOException e1) {
					// TODO Auto-generated catch block
					e1.printStackTrace();
				}
			}
		});
	}


	/**
     * Tests the pull request #38 by @UruDev:
     * Add support for custom writeObject
     */
	@Test
	public void testCustomWriteObject() throws Exception {
		CustomClass writer = new CustomClass();
		writer.start(oos);
	}
}

class SuperAaaa implements Serializable {
	private static final long serialVersionUID = 1L;
	public boolean bool = true;
	public int integer = -1;
	public String superString = "Super!!";
}

class TestConcrete extends SuperAaaa implements Serializable {
	private static final long serialVersionUID = 1L;
	public String childString = "Child!!";

	TestConcrete() {
		super();
	}
}

//Custom writeObject section
class CustomClass implements Serializable {
	private static final long serialVersionUID = 1;

    public void start(ObjectOutputStream out) throws Exception {
        this.writeObject(out);
    }

    private void writeObject(ObjectOutputStream out) throws IOException {
        CustomWriter custom = new CustomWriter(42);
        out.writeObject(custom);
        out.flush();
    }
}

class RandomChild extends Random {
	private static final long serialVersionUID = 1;
    private int num = 1;
    private double doub = 4.5;

    RandomChild(int seed) {
        super(seed);
    }
}

class CustomWriter implements Serializable {
    protected RandomChild custom_obj = null;

    CustomWriter(int seed) {
        custom_obj = new RandomChild(seed);
    }

    private static final long serialVersionUID = 1;
    private static final int CURRENT_SERIAL_VERSION = 0;
    private void writeObject(ObjectOutputStream out) throws IOException {
        out.writeInt(CURRENT_SERIAL_VERSION);
        out.writeObject(custom_obj);
    }
}
