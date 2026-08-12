import java.io.FileOutputStream;
import java.io.IOException;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Generates the fixtures of issue #30: a LinkedHashMap writes its entries in
 * the block data of the HashMap it extends, and its own 'accessOrder' field
 * right after the end of that block data.
 *
 * Reading that block data twice (once as the annotations of the HashMap
 * level, once again in the transformer of the LinkedHashMap) used to
 * desynchronize the stream and to break every field read afterwards.
 *
 * Run it with: java LinkedHashMapExample.java
 */
class LinkedHashMapHolder implements Serializable {
    private static final long serialVersionUID = 1L;

    private String name = "holder";
    private Map<String, String> settings = new LinkedHashMap<String, String>();
    /** Written after the map: it is the field that used to be misread. */
    private int port = 443;

    LinkedHashMapHolder() {
        settings.put("first", "1");
        settings.put("second", "2");
    }
}

public class LinkedHashMapExample {
    public static void main(String[] args) throws IOException {
        // A LinkedHashMap nested in an object, with a field after it
        try (ObjectOutputStream oos = new ObjectOutputStream(
                new FileOutputStream("testLinkedHashMap.ser"))) {
            oos.writeObject(new LinkedHashMapHolder());
        }

        // A LinkedHashMap written on its own
        LinkedHashMap<String, String> bare = new LinkedHashMap<String, String>();
        bare.put("a", "1");
        bare.put("b", "2");
        try (ObjectOutputStream oos = new ObjectOutputStream(
                new FileOutputStream("testBareLinkedHashMap.ser"))) {
            oos.writeObject(bare);
        }
    }
}
