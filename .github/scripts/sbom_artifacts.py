#!/usr/bin/env python
# -- Content-Encoding: UTF-8 --
"""
Records the published artifacts in the SBOM of the project.

``cyclonedx-py`` describes the *resolution* of the dependencies, but it knows
nothing about the files that are actually uploaded to PyPI. This script adds
them to the root component of the SBOM as ``distribution`` external references,
each carrying the SHA-256 digest of the file, so that the SBOM describes the
artifacts that were really shipped rather than a parallel resolution.

Both the JSON and the XML renderings of the SBOM are updated in place.

This script is CI-only tooling and never shipped, so it is Python 3 only.

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
import hashlib
import json
import pathlib
import sys
from xml.etree import ElementTree

# Module version
__version_info__ = (1, 0, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

#: Namespace of the CycloneDX 1.6 XML schema
CYCLONEDX_NS = "http://cyclonedx.org/schema/bom/1.6"

#: Extensions of the published files, i.e. the wheel and the source distribution
DIST_SUFFIXES = (".whl", ".tar.gz")


def digest(path):
    """
    Computes the SHA-256 digest of a file

    :param path: Path to the file to hash
    :return: The digest, as a lowercase hexadecimal string
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(artifacts):
    """
    Describes the given artifacts as (file name, digest) pairs, sorted by name
    so that the SBOM stays reproducible

    :param artifacts: Paths to the published artifacts
    :return: A list of dictionaries with a ``name`` and a ``digest`` entry
    """
    return [
        {"name": path.name, "digest": digest(path)}
        for path in sorted(artifacts, key=lambda p: p.name)
    ]


def update_json(path, artifacts, base_url):
    """
    Adds the artifacts to the root component of a JSON SBOM

    :param path: Path to the JSON SBOM, updated in place
    :param artifacts: Artifacts, as returned by :py:func:`describe`
    :param base_url: URL the artifacts are published under
    """
    with open(path, encoding="utf-8") as fp:
        sbom = json.load(fp)

    component = sbom["metadata"]["component"]
    references = component.setdefault("externalReferences", [])
    for artifact in artifacts:
        references.append(
            {
                "type": "distribution",
                "url": "{0}{1}".format(base_url, artifact["name"]),
                "comment": "published artifact: {0}".format(artifact["name"]),
                "hashes": [{"alg": "SHA-256", "content": artifact["digest"]}],
            }
        )

    with open(path, "w", encoding="utf-8") as fp:
        json.dump(sbom, fp, indent=2, sort_keys=False)
        fp.write("\n")


def update_xml(path, artifacts, base_url):
    """
    Adds the artifacts to the root component of an XML SBOM

    :param path: Path to the XML SBOM, updated in place
    :param artifacts: Artifacts, as returned by :py:func:`describe`
    :param base_url: URL the artifacts are published under
    :raise ValueError: The SBOM has no root component
    """
    ElementTree.register_namespace("", CYCLONEDX_NS)
    tree = ElementTree.parse(path)

    component = tree.getroot().find(
        "{{{0}}}metadata/{{{0}}}component".format(CYCLONEDX_NS)
    )
    if component is None:
        raise ValueError("{0}: no metadata/component element".format(path))

    references = component.find(
        "{{{0}}}externalReferences".format(CYCLONEDX_NS)
    )
    if references is None:
        # The schema orders externalReferences after licenses, which
        # cyclonedx-py always emits
        references = ElementTree.SubElement(
            component, "{{{0}}}externalReferences".format(CYCLONEDX_NS)
        )

    for artifact in artifacts:
        reference = ElementTree.SubElement(
            references,
            "{{{0}}}reference".format(CYCLONEDX_NS),
            {"type": "distribution"},
        )
        # The schema orders the children of a reference: url, comment, hashes
        ElementTree.SubElement(
            reference, "{{{0}}}url".format(CYCLONEDX_NS)
        ).text = "{0}{1}".format(base_url, artifact["name"])
        ElementTree.SubElement(
            reference, "{{{0}}}comment".format(CYCLONEDX_NS)
        ).text = "published artifact: {0}".format(artifact["name"])
        hashes = ElementTree.SubElement(
            reference, "{{{0}}}hashes".format(CYCLONEDX_NS)
        )
        ElementTree.SubElement(
            hashes, "{{{0}}}hash".format(CYCLONEDX_NS), {"alg": "SHA-256"}
        ).text = artifact["digest"]

    ElementTree.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def main():
    """
    Script entry point

    :return: The exit code of the script
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist",
        default="dist",
        help="Directory holding the published artifacts",
    )
    parser.add_argument(
        "--json", dest="json_sbom", help="Path to the JSON SBOM to update"
    )
    parser.add_argument(
        "--xml", dest="xml_sbom", help="Path to the XML SBOM to update"
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="URL prefix the artifacts are downloadable from, e.g. the GitHub "
        "release assets URL. The file name is appended to it",
    )
    args = parser.parse_args()

    # Only the distributions themselves: uv leaves a .gitignore in dist/
    dist = pathlib.Path(args.dist)
    files = [
        path
        for path in dist.iterdir()
        if path.is_file() and path.name.endswith(DIST_SUFFIXES)
    ]
    if not files:
        print(
            "::error::No distribution found in {0}".format(dist),
            file=sys.stderr,
        )
        return 1

    artifacts = describe(files)
    if args.json_sbom:
        update_json(pathlib.Path(args.json_sbom), artifacts, args.base_url)
    if args.xml_sbom:
        update_xml(pathlib.Path(args.xml_sbom), artifacts, args.base_url)

    for artifact in artifacts:
        print("{0}  {1}".format(artifact["digest"], artifact["name"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
