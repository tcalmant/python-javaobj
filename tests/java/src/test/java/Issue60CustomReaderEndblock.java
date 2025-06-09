import java.io.*;
import java.util.List;

class SuperClass implements Serializable {
    private List<String> superItems = null;

    private void writeObject(ObjectOutputStream out) throws IOException {
        out.defaultWriteObject();
        // Custom serialization logic that triggers SC_WRITE_METHOD flag
        out.writeUTF("custom_marker");
    }

    private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
        in.defaultReadObject();
        // Custom deserialization logic
        String marker = in.readUTF();
        System.out.println("Read custom marker: " + marker);
    }
}

class CustomClass extends SuperClass {
    private static final long serialVersionUID = 1L;

    private String name;
    private List<String> items = null;
    private int port = 443;

    public CustomClass(String name) {
        this.name = name;
    }

    private void writeObject(ObjectOutputStream out) throws IOException {
        out.defaultWriteObject();
        // Custom serialization for child class too
        out.writeInt(42);
    }

    private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
        in.defaultReadObject();
        int customValue = in.readInt();
        System.out.println("Read custom value: " + customValue);
    }

    @Override
    public String toString() {
        return "CustomClass{name='" + name + "', items=" + items + "', port=" + port + "}";
    }
}

public class SerializationExample {
    public static void main(String[] args) {
        try {
            // Create and serialize
            CustomClass obj = new CustomClass("test");
            System.out.println("Original: " + obj);

            // Serialize to file
            try (ObjectOutputStream oos = new ObjectOutputStream(new FileOutputStream("issue60_custom_reader_endblock.ser"))) {
                oos.writeObject(obj);
            }

            // Deserialize from file
            try (ObjectInputStream ois = new ObjectInputStream(new FileInputStream("issue60_custom_reader_endblock.ser"))) {
                CustomClass deserialized = (CustomClass) ois.readObject();
                System.out.println("Deserialized: " + deserialized);
            }

        } catch (IOException | ClassNotFoundException e) {
            e.printStackTrace();
        }
    }
}
