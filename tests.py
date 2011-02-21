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
        self.assertEqual(pobj, '\x00C')

    def test_1(self):
        jobj = self.read_file("obj1.ser")
        pobj = javaobj.loads(jobj)
        print pobj
        self.assertEqual(pobj, '\x7f\xef\xff\xff\xff\xff\xff\xff')

    def test_2(self):
        jobj = self.read_file("obj2.ser")
        pobj = javaobj.loads(jobj)
        print pobj
        self.assertEqual(pobj, 'HelloWorld')

    def test_3(self):
        jobj = self.read_file("obj3.ser")
        pobj = javaobj.loads(jobj)
        print pobj
        self.assertEqual(pobj, chr(0))

    def test_4(self):
        jobj = self.read_file("obj4.ser")
        pobj = javaobj.loads(jobj)
        print pobj
        self.assertEqual(pobj, 'HelloWorld')

    def test_5(self):
        jobj = self.read_file("obj5.ser")
        pobj = javaobj.loads(jobj)
        print pobj

        self.assertEqual(pobj.aField1, 'Gabba')
        self.assertEqual(pobj.aField2, None)

    def test_6(self):
        jobj = self.read_file("obj6.ser")
        pobj = javaobj.loads(jobj)
        print pobj
        self.assertEqual(pobj.name, 'java.lang.String')

    def test_7(self):
        jobj = self.read_file("obj7.ser")
        pobj = javaobj.loads(jobj)
        print pobj
        self.assertEqual(pobj.name, 'java.lang.String')

#    def test_choice(self):
#        element = random.choice(self.seq)
#        self.assertTrue(element in self.seq)

if __name__ == '__main__':
    unittest.main()