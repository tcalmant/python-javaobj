import random
import unittest
import javaobj

class TestSequenceFunctions(unittest.TestCase):

    def setUp(self):
        self.seq = range(10)

    def read_file(self, filename):
        file = open(filename, 'rb')
        return file.read()

    def test_0(self):
        jobj = self.read_file("obj0.ser")
        pobj = javaobj.loads(jobj)

        print pobj

        # make sure the shuffled sequence does not lose any elements
        random.shuffle(self.seq)
        self.seq.sort()
        self.assertEqual(self.seq, range(10))

        # should raise an exception for an immutable sequence
        self.assertRaises(TypeError, random.shuffle, (1,2,3))

    def test_choice(self):
        element = random.choice(self.seq)
        self.assertTrue(element in self.seq)


if __name__ == '__main__':
    unittest.main()