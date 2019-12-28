#!/usr/bin/env python3
"""
Definition of the constants used in the deserialization process

:authors: Thomas Calmant
:license: Apache License 2.0
:version: 0.4.0
:status: Alpha

..

    Copyright 2019 Thomas Calmant

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

STREAM_MAGIC = 0xACED
STREAM_VERSION = 0x05

BASE_REFERENCE_IDX = 0x7E0000

TC_NULL = 0x70
TC_REFERENCE = 0x71
TC_CLASSDESC = 0x72
TC_OBJECT = 0x73
TC_STRING = 0x74
TC_ARRAY = 0x75
TC_CLASS = 0x76
TC_BLOCKDATA = 0x77
TC_ENDBLOCKDATA = 0x78
TC_RESET = 0x79
TC_BLOCKDATALONG = 0x7A
TC_EXCEPTION = 0x7B
TC_LONGSTRING = 0x7C
TC_PROXYCLASSDESC = 0x7D
TC_ENUM = 0x7E

SC_WRITE_METHOD = 0x01  # if SC_SERIALIZABLE
SC_BLOCK_DATA = 0x08  # if SC_EXTERNALIZABLE
SC_SERIALIZABLE = 0x02
SC_EXTERNALIZABLE = 0x04
SC_ENUM = 0x10

# type definition chars (typecode)
TYPE_BYTE = ord("B")  # 0x42
TYPE_CHAR = ord("C")  # 0x43
TYPE_DOUBLE = ord("D")  # 0x44
TYPE_FLOAT = ord("F")  # 0x46
TYPE_INTEGER = ord("I")  # 0x49
TYPE_LONG = ord("J")  # 0x4A
TYPE_SHORT = ord("S")  # 0x53
TYPE_BOOLEAN = ord("Z")  # 0x5A
TYPE_OBJECT = ord("L")  # 0x4C
TYPE_ARRAY = ord("[")  # 0x5B

PRIMITIVE_TYPES = (
    TYPE_BYTE,
    TYPE_CHAR,
    TYPE_DOUBLE,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_LONG,
    TYPE_SHORT,
    TYPE_BOOLEAN,
)
