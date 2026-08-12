#!/usr/bin/env python
# -- Content-Encoding: UTF-8 --
"""
Checks that the version of the project is declared consistently everywhere.

javaobj declares its version in many places: ``pyproject.toml`` and, in every
module of ``javaobj``, a ``__version_info__`` tuple and a ``:version:``
docstring field (``setup.py`` has no declaration of its own: on Python 2 it
parses the version out of ``javaobj/__init__.py`` instead of repeating it). A
release bumps around thirty files by hand, so a single missed file is easy:
this script is the guard against it.

Called without argument, it only checks the consistency of the tree. Called
with a version (the release tag), it also checks that the tree declares that
exact version.

This script itself is deliberately Python 3 only (it is CI-only tooling and
never shipped), so it may use ``tomllib`` on 3.11+ with a fallback.

:authors: Thomas Calmant
:license: Apache License 2.0
:version: 1.0.0

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

import argparse
import pathlib
import re
import sys

try:
    # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

#: Matches ``__version_info__ = (0, 6, 0)``
VERSION_INFO_PATTERN = re.compile(
    r"^__version_info__\s*=\s*\(([^)]*)\)", re.MULTILINE
)

#: Matches the ``:version: 0.6.0`` field of a module docstring
VERSION_FIELD_PATTERN = re.compile(r"^:version:\s*(\S+)\s*$", re.MULTILINE)

#: Matches ``version = "0.6.0"`` in pyproject.toml (fallback if tomllib absent)
PYPROJECT_VERSION_PATTERN = re.compile(
    r'^\s*version\s*=\s*"([^"]+)"', re.MULTILINE
)

#: Root of the repository, i.e. the parent of ``.github``
ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Files that carry the version but are not walked as package modules
#: (empty here: setup.py parses the version from javaobj/__init__.py rather
#: than declaring it a second time, so there is nothing extra to check)
EXTRA_FILES = ()


def get_project_version():
    """
    Returns the version declared in ``pyproject.toml``
    """
    path = ROOT / "pyproject.toml"
    if tomllib is not None:
        with open(path, "rb") as fp:
            return str(tomllib.load(fp)["project"]["version"])

    # Fallback for a runner without tomllib: read the first project version
    content = path.read_text(encoding="utf-8")
    match = PYPROJECT_VERSION_PATTERN.search(content)
    if match is None:
        raise ValueError("No version found in pyproject.toml")
    return match.group(1)


def check_module(path, expected):
    """
    Checks the version declarations of a single file

    :param path: Path to the file to check
    :param expected: The version every declaration must match
    :return: A generator of error messages, empty if the file is valid
    """
    content = path.read_text(encoding="utf-8")
    relative = path.relative_to(ROOT)

    match = VERSION_INFO_PATTERN.search(content)
    if match is None:
        # Not every file carries a version: only report the ones that do
        return

    found = ".".join(part.strip() for part in match.group(1).split(","))
    if found != expected:
        yield "{0}: __version_info__ declares {1}, expected {2}".format(
            relative, found, expected
        )

    field = VERSION_FIELD_PATTERN.search(content)
    if field is None:
        yield "{0}: no ':version:' field in the module docstring".format(
            relative
        )
    elif field.group(1) != expected:
        yield "{0}: docstring says ':version: {1}', expected {2}".format(
            relative, field.group(1), expected
        )


def iter_files(package):
    """
    Yields every file that must declare the version

    :param package: Package directory to walk (default: javaobj)
    """
    for path in sorted((ROOT / package).rglob("*.py")):
        yield path

    for name in EXTRA_FILES:
        path = ROOT / name
        if path.exists():
            yield path


def main():
    """
    Script entry point

    :return: The exit code of the script
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tag",
        nargs="?",
        help="Release tag the declared version must match, e.g. 0.6.0",
    )
    parser.add_argument(
        "--package",
        default="javaobj",
        help="Package to walk through (default: javaobj)",
    )
    args = parser.parse_args()

    version = get_project_version()
    if args.tag is not None and args.tag != version:
        print(
            "::error::Tag {0} does not match the version declared in "
            "pyproject.toml ({1})".format(args.tag, version),
            file=sys.stderr,
        )
        return 1

    errors = [
        error
        for path in iter_files(args.package)
        for error in check_module(path, version)
    ]
    if errors:
        for error in errors:
            print("::error::{0}".format(error), file=sys.stderr)
        print(
            "{0} version inconsistencies found".format(len(errors)),
            file=sys.stderr,
        )
        return 1

    print(
        "Version {0} is declared consistently in {1}/ and "
        "pyproject.toml".format(version, args.package)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
