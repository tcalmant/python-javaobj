import random
import unittest
import peiping

class TestEip(unittest.TestCase):

    def simple_generator(self):
        for i in range(10):
            yield i

    def read_file(self, filename):
        file = open(filename, 'rb')
        return file.read()

    def test_0(self):
        print peiping.endpoint(self.simple_generator()).to("")
        peiping.run()


if __name__ == '__main__':
    unittest.main()