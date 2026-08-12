import java.io.FileOutputStream;
import java.io.IOException;
import java.io.ObjectOutputStream;
import java.io.Serializable;

/**
 * Generates the fixture of issue #62: the same array is stored in two
 * fields, so it is written once and referenced the second time with a
 * TC_REFERENCE.
 *
 * Reading it required two fixes in v2: arrays were given a handle but were
 * never stored, so the reference could not be resolved, and a reference
 * found in an array field was read as a class description.
 *
 * The trailing 'marker' field detects a desynchronized stream: it is read
 * right after the shared array.
 *
 * Run it with: java SharedArrayExample.java
 */
class SharedArrayHolder implements Serializable {
    private static final long serialVersionUID = 1L;

    private byte[] first;
    /** Same array as 'first': written as a reference. */
    private byte[] second;
    private String[] strings;
    /** Same array as 'strings': written as a reference. */
    private String[] sameStrings;
    /** Read after the references: wrong if the stream is desynchronized. */
    private int marker = 443;

    SharedArrayHolder() {
        first = new byte[] {1, 2, 3};
        second = first;
        strings = new String[] {"a", "b"};
        sameStrings = strings;
    }
}

public class SharedArrayExample {
    public static void main(String[] args) throws IOException {
        try (ObjectOutputStream oos = new ObjectOutputStream(
                new FileOutputStream("testSharedArray.ser"))) {
            oos.writeObject(new SharedArrayHolder());
        }
    }
}
