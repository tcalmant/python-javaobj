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
import struct
import subprocess
import sys
import unittest
from io import BytesIO

# Prepare Python path to import javaobj
sys.path.insert(0, os.path.abspath(os.path.dirname(os.getcwd())))

import javaobj.v2 as javaobj

# Local
from javaobj.utils import bytes_char, java_data_fd

# ------------------------------------------------------------------------------

# Documentation strings format
__docformat__ = "restructuredtext en"

_logger = logging.getLogger("javaobj.tests")

# ------------------------------------------------------------------------------

# Custom writeObject parsing classes
class CustomWriterInstance(javaobj.beans.JavaInstance):
    def __init__(self):
        javaobj.beans.JavaInstance.__init__(self)

    def load_from_instance(self):
        """
        Updates the content of this instance
        from its parsed fields and annotations
        :return: True on success, False on error
        """
        if self.classdesc and self.classdesc in self.annotations:
            fields = ["int_not_in_fields"] + self.classdesc.fields_names
            raw_data = self.annotations[self.classdesc]
            int_not_in_fields = struct.unpack(
                ">i", BytesIO(raw_data[0].data).read(4)
            )[0]
            custom_obj = raw_data[1]
            values = [int_not_in_fields, custom_obj]
            self.field_data = dict(zip(fields, values))
            return True

        return False


class RandomChildInstance(javaobj.beans.JavaInstance):
    def load_from_instance(self):
        """
        Updates the content of this instance
        from its parsed fields and annotations
        :return: True on success, False on error
        """
        if self.classdesc and self.classdesc in self.field_data:
            fields = self.classdesc.fields_names
            values = [
                self.field_data[self.classdesc][self.classdesc.fields[i]]
                for i in range(len(fields))
            ]
            self.field_data = dict(zip(fields, values))
            if (
                self.classdesc.super_class
                and self.classdesc.super_class in self.annotations
            ):
                super_class = self.annotations[self.classdesc.super_class][0]
                self.annotations = dict(
                    zip(super_class.fields_names, super_class.field_data)
                )
            return True

        return False


class BaseTransformer(javaobj.transformers.ObjectTransformer):
    """
    Creates a JavaInstance object with custom loading methods for the
    classes it can handle
    """

    def __init__(self, handled_classes=None):
        self.instance = None
        self.handled_classes = handled_classes or {}

    def create_instance(self, classdesc):
        """
        Transforms a parsed Java object into a Python object

        :param classdesc: The description of a Java class
        :return: The Python form of the object, or the original JavaObject
        """
        if classdesc.name in self.handled_classes:
            self.instance = self.handled_classes[classdesc.name]()
            return self.instance

        return None


class RandomChildTransformer(BaseTransformer):
    def __init__(self):
        super(RandomChildTransformer, self).__init__(
            {"RandomChild": RandomChildInstance}
        )


class CustomWriterTransformer(BaseTransformer):
    def __init__(self):
        super(CustomWriterTransformer, self).__init__(
            {"CustomWriter": CustomWriterInstance}
        )


class JavaRandomTransformer(BaseTransformer):
    def __init__(self):
        super(JavaRandomTransformer, self).__init__()
        self.name = "java.util.Random"
        self.field_names = ["haveNextNextGaussian", "nextNextGaussian", "seed"]
        self.field_types = [
            javaobj.beans.FieldType.BOOLEAN,
            javaobj.beans.FieldType.DOUBLE,
            javaobj.beans.FieldType.LONG,
        ]

    def load_custom_writeObject(self, parser, reader, name):
        if name != self.name:
            return None

        fields = []
        values = []
        for f_name, f_type in zip(self.field_names, self.field_types):
            values.append(parser._read_field_value(f_type))
            fields.append(javaobj.beans.JavaField(f_type, f_name))

        class_desc = javaobj.beans.JavaClassDesc(
            javaobj.beans.ClassDescType.NORMALCLASS
        )
        class_desc.name = self.name
        class_desc.desc_flags = javaobj.beans.ClassDataType.EXTERNAL_CONTENTS
        class_desc.fields = fields
        class_desc.field_data = values
        return class_desc


# ------------------------------------------------------------------------------


class TestJavaobjV2(unittest.TestCase):
    """
    Full test suite for javaobj V2 Parser
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

    def test_char_rw(self):
        """
        Reads testChar.ser and checks the serialization process
        """
        jobj = self.read_file("testChar.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char object: %s", pobj)
        self.assertEqual(pobj, b"\x00C")

    def test_chars_rw(self):
        """
        Reads testChars.ser and checks the serialization process
        """
        # Expected string as a UTF-16 string
        expected = "python-javaobj".encode("utf-16-be")

        jobj = self.read_file("testChars.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char objects: %s", pobj)
        self.assertEqual(pobj, expected)
        self.assertEqual(pobj, expected.decode("latin1"))

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
        expected = "python-javaobj".encode("utf-16-be")

        jobj = self.read_file("testChars.ser.gz")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read char objects: %s", pobj)
        self.assertEqual(pobj, expected)
        self.assertEqual(pobj, expected.decode("latin1"))

    def test_double_rw(self):
        """
        Reads testDouble.ser and checks the serialization process
        """
        jobj = self.read_file("testDouble.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read double object: %s", pobj)

        self.assertEqual(pobj, b"\x7f\xef\xff\xff\xff\xff\xff\xff")

    def test_bytes_rw(self):
        """
        Reads testBytes.ser and checks the serialization process
        """
        jobj = self.read_file("testBytes.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read bytes: %s", pobj)

        self.assertEqual(pobj, b"HelloWorld")

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
        # in member called '_data.'  I've updated to pass the UTs.
        self.assertEqual(pobj.myArray._data, (1, 3, 7, 11))

    def test_boolean(self):
        """
        Reads testBoolean.ser and checks the serialization process
        """
        jobj = self.read_file("testBoolean.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read boolean object: %s", pobj)

        self.assertEqual(pobj, bytes_char(0))

    def test_byte(self):
        """
        Reads testByte.ser

        The result from javaobj is a single-character string.
        """
        jobj = self.read_file("testByte.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read Byte: %r", pobj)

        self.assertEqual(pobj, bytes_char(127))

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

    def test_class(self):
        """
        Reads the serialized String class
        """
        jobj = self.read_file("testClass.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug("Read object: %s", pobj)
        self.assertEqual(pobj.name, "java.lang.String")

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

    def test_class_array(self):
        """
        Tests the handling of an array of Class objects
        """
        jobj = self.read_file("testClassArray.ser")
        pobj = javaobj.loads(jobj)
        _logger.debug(pobj)
        self.assertEqual(pobj[0].name, "java.lang.Integer")
        self.assertEqual(pobj[1].name, "java.io.ObjectOutputStream")
        self.assertEqual(pobj[2].name, "java.lang.Exception")

    def test_enums(self):
        """
        Tests the handling of "enum" types
        """
        jobj = self.read_file("objEnums.ser")
        pobj = javaobj.loads(jobj)

        classdesc = pobj.get_class()
        _logger.debug("classdesc: {0}".format(classdesc))
        _logger.debug("fields_names: {0}".format(classdesc.fields_names))
        _logger.debug("fields_types: {0}".format(classdesc.fields_types))

        self.assertEqual(classdesc.name, "ClassWithEnum")
        self.assertEqual(pobj.color.classdesc.name, "Color")
        self.assertEqual(pobj.color.constant, u"GREEN")

        for color, intended in zip(pobj.colors, (u"GREEN", u"BLUE", u"RED")):
            _logger.debug("color: {0} - {1}".format(color, type(color)))
            self.assertEqual(color.classdesc.name, "Color")
            self.assertEqual(color.constant, intended)

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
            self.assertIsInstance(obj, javaobj.transformers.JavaTime)

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
        content = javaobj.load(self.read_file("sunExample.ser", stream=True))

        pobj = content[0]
        self.assertEqual(pobj.value, 17)
        self.assertTrue(pobj.next)

        pobj = content[1]
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

    def test_jceks_issue_5(self):
        """
        Tests the handling of JCEKS issue #5
        """
        jobj = self.read_file("jceks_issue_5.ser")
        pobj = javaobj.loads(jobj)
        _logger.info(pobj)

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

    def test_writeObject(self):
        """
        Tests support for custom writeObject (PR #38)
        """

        ser = self.read_file("testCustomWriteObject.ser")
        transformers = [
            CustomWriterTransformer(),
            RandomChildTransformer(),
            JavaRandomTransformer(),
        ]
        pobj = javaobj.loads(ser, *transformers)

        self.assertEqual(isinstance(pobj, CustomWriterInstance), True)
        self.assertEqual(
            isinstance(pobj.field_data["custom_obj"], RandomChildInstance),
            True,
        )

        parent_data = pobj.field_data
        child_data = parent_data["custom_obj"].field_data
        super_data = parent_data["custom_obj"].annotations
        expected = {
            "int_not_in_fields": 0,
            "custom_obj": {
                "field_data": {"doub": 4.5, "num": 1},
                "annotations": {
                    "haveNextNextGaussian": False,
                    "nextNextGaussian": 0.0,
                    "seed": 25214903879,
                },
            },
        }

        self.assertEqual(
            expected["int_not_in_fields"], parent_data["int_not_in_fields"]
        )
        self.assertEqual(expected["custom_obj"]["field_data"], child_data)
        self.assertEqual(expected["custom_obj"]["annotations"], super_data)


# ------------------------------------------------------------------------------


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Run tests
    unittest.main()
