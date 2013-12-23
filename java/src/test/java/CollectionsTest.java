import java.io.FileOutputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.LinkedList;
import java.util.Map;
import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;

import org.junit.Test;

class CollectionsSerializableBean implements Serializable {
	/**
	 * 
	 */
	private static final long serialVersionUID = 1L;

	// Collections
	public Collection<String> arrayList;
	public Map<String, Object> hashMap;
	public Collection<String> linkedList;
	public Queue<String> queue;

	public CollectionsSerializableBean() {
		super();

		arrayList = new ArrayList<String>();
		arrayList.add("e1");
		arrayList.add("e2");

		linkedList = new LinkedList<String>();
		linkedList.add("ll1");
		linkedList.add("ll2");

		hashMap = new HashMap<String, Object>();
		hashMap.put("k1", null);
		hashMap.put("k2", "value2");
		hashMap.put("k3", arrayList);
		hashMap.put("k3", linkedList);

		queue = new ConcurrentLinkedQueue<String>();
		queue.add("q1");
		queue.add("q2");
		queue.add("q3");
	}
}

public class CollectionsTest {

	FileOutputStream fos;
	ObjectOutputStream oos;

	@Test
	public void testCollections() throws Exception {
		oos = new ObjectOutputStream(fos = new FileOutputStream(
				"objCollections.ser"));
		oos.writeObject(new CollectionsSerializableBean());
		oos.flush();
	}
}
