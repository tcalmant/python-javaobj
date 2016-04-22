#!/usr/bin/python
# -- Content-Encoding: UTF-8 --
"""
Tests for javaobj

See:
http://download.oracle.com/javase/6/docs/platform/serialization/spec/protocol.html

:authors: Volodymyr Buell, Thomas Calmant
:license: Apache License 2.0
:version: 0.1.1
:status: Alpha

..

    Copyright 2013 Thomas Calmant

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

# Standard library
import logging
import subprocess
import unittest
import os
import sys

# Prepare Python path to import javaobj
sys.path.insert(0, os.path.abspath(os.path.dirname(os.getcwd())))

# Local
import javaobj

# ------------------------------------------------------------------------------

# Documentation strings format
__docformat__ = "restructuredtext en"

_logger = logging.getLogger("javaobj.tests")

# ------------------------------------------------------------------------------


class TestJavaobj(unittest.TestCase):
    """
    Full test suite for javaobj
    """
    @classmethod
    def setUpClass(cls):
        """
        Calls Maven to compile & run Java classes that will generate serialized
        data
        """
        # Compute the java directory (from top folder or test folder)
        java_dir = [os.getcwd()]
        if not os.getcwd().endswith('tests'):
            # Not in the test folder
            java_dir.append('tests')

        java_dir.append('java')

        os.chdir(os.path.join(*java_dir))
        subprocess.call(['mvn', 'test'], shell=True)
        os.chdir('..')

    def read_file(self, filename):
        """
        Reads the content of the given file in binary mode

        :param filename: Name of the file to read
        :return: File content
        """
        with open(filename, 'rb') as filep:
            return filep.read()

    def test_char_rw(self):
        """
        Reads testChar.ser and checks the serialization process
        """
        jobj = self.read_file("java/testChar.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char object: %s", pobj)
        self.assertEqual(pobj, '\x00C')
        jobj_ = javaobj.dumps(pobj)
        self.assertEqual(jobj, jobj_)

    def test_double_rw(self):
        """
        Reads testDouble.ser and checks the serialization process
        """
        jobj = self.read_file("java/testDouble.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read double object: %s", pobj)

        self.assertEqual(pobj, '\x7f\xef\xff\xff\xff\xff\xff\xff')

        jobj_ = javaobj.dumps(pobj)
        self.assertEqual(jobj, jobj_)

    def test_bytes_rw(self):
        """
        Reads testBytes.ser and checks the serialization process
        """
        jobj = self.read_file("java/testBytes.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read bytes: %s", pobj)

        self.assertEqual(pobj, 'HelloWorld')

        jobj_ = javaobj.dumps(pobj)
        self.assertEqual(jobj, jobj_)

    def test_boolean(self):
        """
        Reads testBoolean.ser and checks the serialization process
        """
        jobj = self.read_file("java/testBoolean.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read boolean object: %s", pobj)

        self.assertEqual(pobj, chr(0))

        jobj_ = javaobj.dumps(pobj)
        self.assertEqual(jobj, jobj_)

    def test_byte(self):
        """
        Reads testByte.ser

        The result from javaobj is a single-character string.
        """
        jobj = self.read_file("java/testByte.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read Byte: %r", pobj)

        self.assertEqual(pobj, chr(127))

        jobj_ = javaobj.dumps(pobj)
        self.assertEqual(jobj, jobj_)

    def test_fields(self):
        """
        Reads a serialized object and checks its fields
        """
        jobj = self.read_file("java/test_readFields.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read object: %s", pobj)

        self.assertEqual(pobj.aField1, 'Gabba')
        self.assertEqual(pobj.aField2, None)

        classdesc = pobj.get_class()
        self.assertTrue(classdesc)
        self.assertEqual(classdesc.serialVersionUID, 0x7F0941F5)
        self.assertEqual(classdesc.name, "OneTest$SerializableTestHelper")

        _logger.debug("Class..........: %s", classdesc)
        _logger.debug(".. Flags.......: %s", classdesc.flags)
        _logger.debug(".. Fields Names: %s", classdesc.fields_names)
        _logger.debug(".. Fields Types: %s", classdesc.fields_types)

        self.assertEqual(len(classdesc.fields_names), 3)

#        jobj_ = javaobj.dumps(pobj)
#        self.assertEqual(jobj, jobj_)

    def test_class(self):
        """
        Reads the serialized String class
        """
        jobj = self.read_file("java/testClass.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read object: %s", pobj)
        self.assertEqual(pobj.name, 'java.lang.String')

#        jobj_ = javaobj.dumps(pobj)
#        self.assertEqual(jobj, jobj_)

#     def test_swing_object(self):
#         """
#         Reads a serialized Swing component
#         """
#         jobj = self.read_file("java/testSwingObject.ser")
#         pobj = javaobj.loads(jobj)
#         _logger.debug("Read object: %s", pobj)
#
#         classdesc = pobj.get_class()
#         _logger.debug("Class..........: %s", classdesc)
#         _logger.debug(".. Fields Names: %s", classdesc.fields_names)
#         _logger.debug(".. Fields Types: %s", classdesc.fields_types)

#    def test_super(self):
#        jobj = self.read_file("objSuper.ser")
#        pobj = javaobj.loads(jobj)
#        print pobj
#
#        classdesc = pobj.get_class()
#        print classdesc
#        print classdesc.fields_names
#        print classdesc.fields_types
#
#        print pobj.childString
#        print pobj.bool
#        print pobj.integer
#
#    def test_arrays(self):
#        jobj = self.read_file("objArrays.ser")
#        pobj = javaobj.loads(jobj)
#        print pobj
#
#        classdesc = pobj.get_class()
#        print classdesc
#        print classdesc.fields_names
#        print classdesc.fields_types
#
# #        public String[] stringArr = {"1", "2", "3"};
# #        public int[] integerArr = {1,2,3};
# #        public boolean[] boolArr = {true, false, true};
# #        public TestConcrete[] concreteArr = {new TestConcrete(), new TestConcrete()};
#
#        print pobj.stringArr
#        print pobj.integerArr
#        print pobj.boolArr
#        print pobj.concreteArr
#
#    def test_enums(self):
#        jobj = self.read_file("objEnums.ser")
#        pobj = javaobj.loads(jobj)
#        print pobj
#
#        classdesc = pobj.get_class()
#        print classdesc
#        print classdesc.fields_names
#        print classdesc.fields_types
#
#    def test_exception(self):
#        jobj = self.read_file("objException.ser")
#        pobj = javaobj.loads(jobj)
#        print pobj
#
#        classdesc = pobj.get_class()
#        print classdesc
#        print classdesc.fields_names
#        print classdesc.fields_types
#
#    def test_sun_example(self):
#        marshaller = javaobj.JavaObjectUnmarshaller(open("sunExample.ser"))
#        pobj = marshaller.readObject()
#
#        self.assertEqual(pobj.value, 17)
#        self.assertTrue(pobj.next)
#
#        pobj = marshaller.readObject()
#
#        self.assertEqual(pobj.value, 19)
#        self.assertFalse(pobj.next)
#
    def test_collections(self):
        jobj = self.read_file("objCollections.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        _logger.debug("arrayList: %s", pobj.arrayList)
        self.assertTrue(isinstance(pobj.arrayList, list))
        _logger.debug("hashMap: %s", pobj.hashMap)
        self.assertTrue(isinstance(pobj.hashMap, dict))
        _logger.debug("linkedList: %s", pobj.linkedList)
        self.assertTrue(isinstance(pobj.linkedList, list))

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Run tests
    unittest.main()
