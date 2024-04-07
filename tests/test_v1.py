#!/usr/bin/python
# -- Content-Encoding: utf-8 --
"""
Tests for javaobj

See:
http://download.oracle.com/javase/6/docs/platform/serialization/spec/protocol.html

:authors: Volodymyr Buell, Thomas Calmant
:license: Apache License 2.0
:version: 0.4.4
:status: Alpha

..

    Copyright 2024 Thomas Calmant

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

# Print is used in tests
from __future__ import print_function

# Standard library
import logging
import os
import subprocess
import sys
import unittest

# Prepare Python path to import javaobj
sys.path.insert(0, os.path.abspath(os.path.dirname(os.getcwd())))

# Local
import javaobj.v1 as javaobj
from javaobj.utils import hexdump, java_data_fd

# ------------------------------------------------------------------------------

# Documentation strings format
__docformat__ = "restructuredtext en"

_logger = logging.getLogger("javaobj.tests")

# ------------------------------------------------------------------------------


class TestJavaobjV1(unittest.TestCase):
    """
    Full test suite for javaobj V1 parser
    """

    @classmethod
    def setUpClass(cls):
        """
        Calls Maven to compile & run Java classes that will generate serialized
        data
        """
        # Compute the java directory
        java_dir = os.path.join(os.path.dirname(__file__), "java")

        if not os.getenv("JAVAOBJ_NO_MAVEN"):
            # Run Maven and go back to the working folder
            cwd = os.getcwd()
            os.chdir(java_dir)
            subprocess.call("mvn test", shell=True)
            os.chdir(cwd)

    def read_file(self, filename, stream=False):
        """
        Reads the content of the given file in binary mode

        :param filename: Name of the file to read
        :param stream: If True, return the file stream
        :return: File content or stream
        """
        for subfolder in ("java", ""):
            found_file = os.path.join(
                os.path.dirname(__file__), subfolder, filename
            )
            if os.path.exists(found_file):
                break
        else:
            raise IOError("File not found: {0}".format(filename))

        if stream:
            return open(found_file, "rb")
        else:
            with open(found_file, "rb") as filep:
                return filep.read()

    def _try_marshalling(self, original_stream, original_object):
        """
        Tries to marshall an object and compares it to the original stream
        """
        _logger.debug("Try Marshalling")
        marshalled_stream = javaobj.dumps(original_object)
        # Reloading the new dump allows to compare the decoding sequence
        try:
            javaobj.loads(marshalled_stream)
            self.assertEqual(original_stream, marshalled_stream)
        except Exception:
            print("-" * 80)
            print("=" * 30, "Original", "=" * 30)
            print(hexdump(original_stream))
            print("*" * 30, "Marshalled", "*" * 30)
            print(hexdump(marshalled_stream))
            print("-" * 80)
            raise

    def test_char_rw(self):
        """
        Reads testChar.ser and checks the serialization process
        """
        jobj = self.read_file("testChar.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char object: %s", pobj)
        self.assertEqual(pobj, "\x00C")
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

    def test_gzip_open(self):
        """
        Tests if the GZip auto-uncompress works
        """
        with java_data_fd(self.read_file("testChars.ser", stream=True)) as fd:
            base = fd.read()

        with java_data_fd(
            self.read_file("testChars.ser.gz", stream=True)
        ) as fd:
            gzipped = fd.read()

        self.assertEqual(
            base, gzipped, "Uncompressed content doesn't match the original"
        )

    def test_chars_gzip(self):
        """
        Reads testChars.ser.gz
        """
        # Expected string as a UTF-16 string
        expected = "python-javaobj".encode("utf-16-be").decode("latin1")

        jobj = self.read_file("testChars.ser.gz")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char objects: %s", pobj)
        self.assertEqual(pobj, expected)

    def test_double_rw(self):
        """
        Reads testDouble.ser and checks the serialization process
        """
        jobj = self.read_file("testDouble.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read double object: %s", pobj)

        self.assertEqual(pobj, "\x7f\xef\xff\xff\xff\xff\xff\xff")
        self._try_marshalling(jobj, pobj)

    def test_bytes_rw(self):
        """
        Reads testBytes.ser and checks the serialization process
        """
        jobj = self.read_file("testBytes.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read bytes: %s", pobj)

        self.assertEqual(pobj, "HelloWorld")
        self._try_marshalling(jobj, pobj)

    def test_class_with_byte_array_rw(self):
        """
        Tests handling of classes containing a Byte Array
        """
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

        self.assertEqual(pobj.aField1, u"Gabba")
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
        self.assertEqual(pobj.name, "java.lang.String")
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
        """
        Tests basic class inheritance handling
        """
        jobj = self.read_file("objSuper.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        classdesc = pobj.get_class()
        _logger.debug(classdesc)
        _logger.debug(classdesc.fields_names)
        _logger.debug(classdesc.fields_types)

        self.assertEqual(pobj.childString, u"Child!!")
        self.assertEqual(pobj.bool, True)
        self.assertEqual(pobj.integer, -1)
        self.assertEqual(pobj.superString, u"Super!!")

        self._try_marshalling(jobj, pobj)

    def test_arrays(self):
        """
        Tests handling of Java arrays
        """
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

    def test_japan(self):
        """
        Tests the UTF encoding handling with Japanese characters
        """
        # Japan.ser contains a string using wide characters: the name of the
        # state from Japan (according to wikipedia)
        jobj = self.read_file("testJapan.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)
        # Compare the UTF-8 encoded version of the name
        self.assertEqual(
            pobj, b"\xe6\x97\xa5\xe6\x9c\xac\xe5\x9b\xbd".decode("utf-8")
        )
        self._try_marshalling(jobj, pobj)

    def test_char_array(self):
        """
        Tests the loading of a wide-char array
        """
        jobj = self.read_file("testCharArray.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)
        self.assertEqual(
            pobj,
            [
                u"\u0000",
                u"\ud800",
                u"\u0001",
                u"\udc00",
                u"\u0002",
                u"\uffff",
                u"\u0003",
            ],
        )
        self._try_marshalling(jobj, pobj)

    def test_2d_array(self):
        """
        Tests the handling of a 2D array
        """
        jobj = self.read_file("test2DArray.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)
        self.assertEqual(
            pobj, [[1, 2, 3], [4, 5, 6],],
        )

    def test_enums(self):
        """
        Tests the handling of "enum" types
        """
        jobj = self.read_file("objEnums.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        classdesc = pobj.get_class()
        _logger.debug(classdesc)
        _logger.debug(classdesc.fields_names)
        _logger.debug(classdesc.fields_types)

        self.assertEqual(classdesc.name, "ClassWithEnum")
        self.assertEqual(pobj.color.classdesc.name, "Color")
        self.assertEqual(pobj.color.constant, u"GREEN")

        for color, intended in zip(pobj.colors, (u"GREEN", u"BLUE", u"RED")):
            self.assertEqual(color.classdesc.name, "Color")
            self.assertEqual(color.constant, intended)

            # self._try_marshalling(jobj, pobj)

    def test_sets(self):
        """
        Tests handling of HashSet and TreeSet
        """
        for filename in (
            "testHashSet.ser",
            "testTreeSet.ser",
            "testLinkedHashSet.ser",
        ):
            _logger.debug("Loading file: %s", filename)
            jobj = self.read_file(filename)
            pobj = javaobj.loads(jobj)
            _logger.debug(pobj)
            self.assertIsInstance(pobj, set)
            self.assertSetEqual({i.value for i in pobj}, {1, 2, 42})

    def test_times(self):
        """
        Tests the handling of java.time classes
        """
        jobj = self.read_file("testTime.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        # First one is a duration of 10s
        duration = pobj[0]
        self.assertEqual(duration.second, 10)

        # Check types
        self.assertIsInstance(pobj, javaobj.beans.JavaArray)
        for obj in pobj:
            self.assertIsInstance(
                obj, javaobj.DefaultObjectTransformer.JavaTime
            )

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
            self.read_file("sunExample.ser", stream=True)
        )
        pobj = marshaller.readObject()

        self.assertEqual(pobj.value, 17)
        self.assertTrue(pobj.next)

        pobj = marshaller.readObject()

        self.assertEqual(pobj.value, 19)
        self.assertFalse(pobj.next)

    def test_collections(self):
        """
        Tests the handling of ArrayList, LinkedList and HashMap
        """
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
        """
        Tests the handling of JCEKS issue #5
        """
        jobj = self.read_file("jceks_issue_5.ser")
        pobj = javaobj.loads(jobj)
        _logger.info(pobj)
        # self._try_marshalling(jobj, pobj)

    def test_qistoph_pr_27(self):
        """
        Tests support for Bool, Integer, Long classes (PR #27)
        """
        # Load the basic map
        jobj = self.read_file("testBoolIntLong.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)

        # Basic checking
        self.assertEqual(pobj[u"key1"], u"value1")
        self.assertEqual(pobj[u"key2"], u"value2")
        self.assertEqual(pobj[u"int"], 9)
        self.assertEqual(pobj[u"int2"], 10)
        self.assertEqual(pobj[u"bool"], True)
        self.assertEqual(pobj[u"bool2"], True)

        # Load the parent map
        jobj2 = self.read_file("testBoolIntLong-2.ser")
        pobj2 = javaobj.loads(jobj2)
        _logger.debug(pobj2)

        parent_map = pobj2[u"subMap"]
        for key, value in pobj.items():
            self.assertEqual(parent_map[key], value)


# ------------------------------------------------------------------------------


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Run tests
    unittest.main()
