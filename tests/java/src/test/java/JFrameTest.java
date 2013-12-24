import java.awt.BorderLayout;
import java.awt.Component;
import java.awt.GridLayout;
import java.awt.Rectangle;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.awt.event.MouseAdapter;
import java.awt.event.MouseEvent;
import java.awt.event.WindowAdapter;
import java.awt.event.WindowEvent;
import java.io.Serializable;

import javax.swing.JButton;
import javax.swing.JCheckBox;
import javax.swing.JFrame;
import javax.swing.JList;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.ListCellRenderer;
import javax.swing.ListModel;
import javax.swing.ListSelectionModel;
import javax.swing.UIManager;
import javax.swing.border.EmptyBorder;

public class JFrameTest extends JFrame {

	class CheckableItem implements Serializable {
		/**
		 * 
		 */
		private static final long serialVersionUID = 1L;

		private boolean isSelected;

		private final String str;

		public CheckableItem(final String str) {
			this.str = str;
			isSelected = false;
		}

		public boolean isSelected() {
			return isSelected;
		}

		public void setSelected(final boolean b) {
			isSelected = b;
		}

		@Override
		public String toString() {
			return str;
		}
	}

	class CheckListRenderer extends JCheckBox implements
			ListCellRenderer<CheckableItem> {

		/**
		 * 
		 */
		private static final long serialVersionUID = 1L;

		public CheckListRenderer() {
			setBackground(UIManager.getColor("List.textBackground"));
			setForeground(UIManager.getColor("List.textForeground"));
		}

		@Override
		public Component getListCellRendererComponent(
				final JList<? extends CheckableItem> list,
				final CheckableItem value, final int index,
				final boolean isSelected, final boolean hasFocus) {
			setEnabled(list.isEnabled());
			setSelected(value.isSelected());
			setFont(list.getFont());
			setText(value.toString());
			return this;
		}
	}

	/**
	 * 
	 */
	private static final long serialVersionUID = 1L;

	public static void main(final String args[]) {

		final JFrameTest frame = new JFrameTest();
		frame.addWindowListener(new WindowAdapter() {
			@Override
			public void windowClosing(final WindowEvent e) {
				System.exit(0);
			}
		});
		frame.setSize(300, 200);
		frame.setVisible(true);
	}

	public JFrameTest() {
		super("CheckList Example");
		final String[] strs = { "swing", "home", "basic", "metal", "JList" };

		final JList<CheckableItem> list = new JList<CheckableItem>(
				createData(strs));

		list.setCellRenderer(new CheckListRenderer());
		list.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);
		list.setBorder(new EmptyBorder(0, 4, 0, 0));
		list.addMouseListener(new MouseAdapter() {
			@Override
			public void mouseClicked(final MouseEvent e) {
				final int index = list.locationToIndex(e.getPoint());
				final CheckableItem item = list.getModel().getElementAt(index);
				item.setSelected(!item.isSelected());
				final Rectangle rect = list.getCellBounds(index, index);
				list.repaint(rect);
			}
		});
		final JScrollPane sp = new JScrollPane(list);

		final JTextArea textArea = new JTextArea(3, 10);
		final JScrollPane textPanel = new JScrollPane(textArea);
		final JButton printButton = new JButton("print");
		printButton.addActionListener(new ActionListener() {
			@Override
			public void actionPerformed(final ActionEvent e) {
				final ListModel<CheckableItem> model = list.getModel();
				final int n = model.getSize();
				for (int i = 0; i < n; i++) {
					final CheckableItem item = model.getElementAt(i);
					if (item.isSelected()) {
						textArea.append(item.toString());
						textArea.append(System.getProperty("line.separator"));
					}
				}
			}
		});
		final JButton clearButton = new JButton("clear");
		clearButton.addActionListener(new ActionListener() {
			@Override
			public void actionPerformed(final ActionEvent e) {
				textArea.setText("");
			}
		});
		final JPanel panel = new JPanel(new GridLayout(2, 1));
		panel.add(printButton);
		panel.add(clearButton);

		getContentPane().add(sp, BorderLayout.CENTER);
		getContentPane().add(panel, BorderLayout.EAST);
		getContentPane().add(textPanel, BorderLayout.SOUTH);
	}

	private CheckableItem[] createData(final String[] strs) {
		final int n = strs.length;
		final CheckableItem[] items = new CheckableItem[n];
		for (int i = 0; i < n; i++) {
			items[i] = new CheckableItem(strs[i]);
		}
		return items;
	}
}