#!/usr/bin/python
# -- Content-Encoding: UTF-8 --
"""
Tests for javaobj

See:
http://download.oracle.com/javase/6/docs/platform/serialization/spec/protocol.html

:authors: Volodymyr Buell, Thomas Calmant
:license: Apache License 2.0
:version: 0.2.3
:status: Alpha

..

    Copyright 2016 Thomas Calmant

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
        # Compute the java directory
        java_dir = os.path.join(os.path.dirname(__file__), 'java')

        # Run Maven and go back to the working folder
        cwd = os.getcwd()
        os.chdir(java_dir)
        subprocess.call('mvn test', shell=True)
        os.chdir(cwd)

    def read_file(self, filename, stream=False):
        """
        Reads the content of the given file in binary mode

        :param filename: Name of the file to read
        :param stream: If True, return the file stream
        :return: File content or stream
        """
        for subfolder in ('java', ''):
            found_file = os.path.join(
                os.path.dirname(__file__), subfolder, filename)
            if os.path.exists(found_file):
                break
        else:
            raise IOError("File not found: {0}".format(filename))

        if stream:
            return open(found_file, "rb")
        else:
            with open(found_file, 'rb') as filep:
                return filep.read()

    def _try_marshalling(self, original_stream, original_object):
        """
        Tries to marshall an object and compares it to the original stream
        """
        marshalled_stream = javaobj.dumps(original_object)
        # Reloading the new dump allows to compare the decoding sequence
        try:
            javaobj.loads(marshalled_stream)
            self.assertEqual(original_stream, marshalled_stream)
        except:
            print("-" * 80)
            print("=" * 30, "Original", "=" * 30)
            print(javaobj.JavaObjectUnmarshaller._create_hexdump(
                original_stream))
            print("*" * 30, "Marshalled", "*" * 30)
            print(javaobj.JavaObjectUnmarshaller._create_hexdump(
                marshalled_stream))
            print("-" * 80)
            raise

    def test_char_rw(self):
        """
        Reads testChar.ser and checks the serialization process
        """
        jobj = self.read_file("testChar.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char object: %s", pobj)
        self.assertEqual(pobj, '\x00C')
        self._try_marshalling(jobj, pobj)

    def test_chars_rw(self):
        """
        Reads testChars.ser and checks the serialization process
        """
        # Expected string as a UTF-16 string
        expected = "python-javaobj".encode("utf-16-be").decode("latin1")

        jobj = self.read_file("testChars.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char objects: %s", pobj)
        self.assertEqual(pobj, expected)
        self._try_marshalling(jobj, pobj)

    def test_double_rw(self):
        """
        Reads testDouble.ser and checks the serialization process
        """
        jobj = self.read_file("testDouble.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read double object: %s", pobj)

        self.assertEqual(pobj, '\x7f\xef\xff\xff\xff\xff\xff\xff')
        self._try_marshalling(jobj, pobj)

    def test_bytes_rw(self):
        """
        Reads testBytes.ser and checks the serialization process
        """
        jobj = self.read_file("testBytes.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read bytes: %s", pobj)

        self.assertEqual(pobj, 'HelloWorld')
        self._try_marshalling(jobj, pobj)

    def test_class_with_byte_array_rw(self):
        jobj = self.read_file("testClassWithByteArray.ser")
        pobj = javaobj.loads(jobj)

	# j8spencer (Google, LLC) 2018-01-16:  It seems specific support for 
        # byte arrays was added, but is a little out-of-step with the other
        # types in terms of style.  This UT was broken, since the "myArray"
        # member has the array stored as a tuple of ints (not a byte string)
        # in memeber called '_data.'  I've updated to pass the UTs.
        self.assertEqual(pobj.myArray._data, (1, 3, 7, 11))
        self._try_marshalling(jobj, pobj)

    def test_boolean(self):
        """
        Reads testBoolean.ser and checks the serialization process
        """
        jobj = self.read_file("testBoolean.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read boolean object: %s", pobj)

        self.assertEqual(pobj, chr(0))
        self._try_marshalling(jobj, pobj)

    def test_byte(self):
        """
        Reads testByte.ser

        The result from javaobj is a single-character string.
        """
        jobj = self.read_file("testByte.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read Byte: %r", pobj)

        self.assertEqual(pobj, chr(127))
        self._try_marshalling(jobj, pobj)

    def test_fields(self):
        """
        Reads a serialized object and checks its fields
        """
        jobj = self.read_file("test_readFields.ser")
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
        self._try_marshalling(jobj, pobj)

    def test_class(self):
        """
        Reads the serialized String class
        """
        jobj = self.read_file("testClass.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read object: %s", pobj)
        self.assertEqual(pobj.name, 'java.lang.String')
        self._try_marshalling(jobj, pobj)

    # def test_swing_object(self):
    #     """
    #     Reads a serialized Swing component
    #     """
    #     jobj = self.read_file("testSwingObject.ser")
    #     pobj = javaobj.loads(jobj)
    #     _logger.debug("Read object: %s", pobj)
    #
    #     classdesc = pobj.get_class()
    #     _logger.debug("Class..........: %s", classdesc)
    #     _logger.debug(".. Fields Names: %s", classdesc.fields_names)
    #     _logger.debug(".. Fields Types: %s", classdesc.fields_types)

    def test_super(self):
        jobj = self.read_file("objSuper.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        classdesc = pobj.get_class()
        _logger.debug(classdesc)
        _logger.debug(classdesc.fields_names)
        _logger.debug(classdesc.fields_types)

        self.assertEqual(pobj.childString, "Child!!")
        self.assertEqual(pobj.bool, True)
        self.assertEqual(pobj.integer, -1)
        self.assertEqual(pobj.superString, "Super!!")

        self._try_marshalling(jobj, pobj)

    def test_arrays(self):
        jobj = self.read_file("objArrays.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        classdesc = pobj.get_class()
        _logger.debug(classdesc)
        _logger.debug(classdesc.fields_names)
        _logger.debug(classdesc.fields_types)

        # public String[] stringArr = {"1", "2", "3"};
        # public int[] integerArr = {1,2,3};
        # public boolean[] boolArr = {true, false, true};
        # public TestConcrete[] concreteArr = {new TestConcrete(),
        #                                      new TestConcrete()};

        _logger.debug(pobj.stringArr)
        _logger.debug(pobj.integerArr)
        _logger.debug(pobj.boolArr)
        _logger.debug(pobj.concreteArr)

        self._try_marshalling(jobj, pobj)

    def test_enums(self):
        jobj = self.read_file("objEnums.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        classdesc = pobj.get_class()
        _logger.debug(classdesc)
        _logger.debug(classdesc.fields_names)
        _logger.debug(classdesc.fields_types)

        self.assertEqual(classdesc.name, "ClassWithEnum")
        self.assertEqual(pobj.color.classdesc.name, "Color")
        self.assertEqual(pobj.color.constant, "GREEN")

        for color, intended in zip(pobj.colors, ("GREEN", "BLUE", "RED")):
            self.assertEqual(color.classdesc.name, "Color")
            self.assertEqual(color.constant, intended)

            # self._try_marshalling(jobj, pobj)

    # def test_exception(self):
    #     jobj = self.read_file("objException.ser")
    #     pobj = javaobj.loads(jobj)
    #     _logger.debug(pobj)
    #
    #     classdesc = pobj.get_class()
    #     _logger.debug(classdesc)
    #     _logger.debug(classdesc.fields_names)
    #     _logger.debug(classdesc.fields_types)
    #
    #     # TODO: add some tests
    #     self.assertEqual(classdesc.name, "MyExceptionWhenDumping")

    def test_sun_example(self):
       marshaller = javaobj.JavaObjectUnmarshaller(
           self.read_file("sunExample.ser", stream=True))
       pobj = marshaller.readObject()

       self.assertEqual(pobj.value, 17)
       self.assertTrue(pobj.next)

       pobj = marshaller.readObject()

       self.assertEqual(pobj.value, 19)
       self.assertFalse(pobj.next)

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

        # FIXME: referencing problems with the collection class
        # self._try_marshalling(jobj, pobj)

    def test_jceks_issue_5(self):
        jobj = self.read_file("jceks_issue_5.ser")
        pobj = javaobj.loads(jobj)
        _logger.info(pobj)
        # self._try_marshalling(jobj, pobj)

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Run tests
    unittest.main()
