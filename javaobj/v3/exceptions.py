#!/usr/bin/env python3
"""
Exception hierarchy for javaobj v3.

:authors: Thomas Calmant
:license: Apache License 2.0
:version: 0.5.0
:status: Alpha

..

    Copyright 2026 Thomas Calmant

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

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 5, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------

__all__ = [
    "JavaObjError",
    "ParseError",
    "UnexpectedOpcodeError",
    "UnsupportedFeatureError",
    "SecurityError",
]


class JavaObjError(Exception):
    """Base exception for all javaobj v3 errors."""


class ParseError(JavaObjError):
    """Raised when the stream cannot be decoded according to the protocol."""

    def __init__(self, message: str, offset: int = -1) -> None:
        """
        :param message: Human-readable description of the problem.
        :param offset: Byte offset in the stream where the error occurred,
                       or -1 if unknown.
        """
        super().__init__(message)
        self.offset = offset

    def __str__(self) -> str:
        base = super().__str__()
        if self.offset >= 0:
            return f"{base} (at stream offset 0x{self.offset:x})"
        return base


class UnexpectedOpcodeError(ParseError):
    """
    Raised when an opcode byte is not among the set of expected values.

    Attributes:
        expected: Tuple of acceptable opcode values.
        got: The opcode that was actually read.
    """

    def __init__(
        self,
        expected: tuple[int, ...],
        got: int,
        offset: int = -1,
    ) -> None:
        expected_hex = [f"0x{e:02x}" for e in expected]
        super().__init__(
            f"Expected one of {expected_hex}, got 0x{got:02x}",
            offset,
        )
        self.expected = expected
        self.got = got


class UnsupportedFeatureError(JavaObjError):
    """Raised when the stream uses a feature not yet implemented in v3."""


class SecurityError(JavaObjError):
    """
    Raised when a configurable safety limit is exceeded.

    This guards against malicious streams that declare huge arrays, deeply
    nested object graphs, or extremely long strings to exhaust memory or
    the call stack.
    """
