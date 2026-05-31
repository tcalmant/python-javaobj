#!/usr/bin/env python3
"""
Migration helpers from javaobj v1 / v2 to v3

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

# Standard library
from typing import Any

# Javaobj
from .beans import (
    FieldType,
    JavaArray,
    JavaClassDesc,
    JavaEnum,
    JavaField,
    JavaInstance,
    JavaString,
    ParsedContent,
)
from .exceptions import JavaObjError

# ------------------------------------------------------------------------------

# Module version
__version_info__ = (0, 5, 0)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------

__all__ = [
    "v2_to_v3",
    "v1_to_v3",
    "V1CompatMixin",
    "V2CompatMixin",
]


# ------------------------------------------------------------------------------
# v2 → v3 adapter
# ------------------------------------------------------------------------------


def v2_to_v3(v2_obj: Any) -> ParsedContent:
    """
    Converts a javaobj **v2** top-level object to the nearest v3 equivalent.

    For types that map directly (e.g. ``javaobj.v2.beans.JavaInstance`` →
    ``javaobj.v3.beans.JavaInstance``) the fields are copied shallowly.
    Nested objects are **not** recursively converted — only the top-level
    wrapper is adapted.

    :param v2_obj: A parsed object returned by :func:`javaobj.v2.load` or
                   :func:`javaobj.v2.loads`.
    :return: The v3 equivalent object.
    :raises JavaObjError: If the type cannot be mapped.
    """
    try:
        from javaobj.v2.beans import (
            JavaArray as V2Array,
        )
        from javaobj.v2.beans import (
            JavaEnum as V2Enum,
        )
        from javaobj.v2.beans import (  # type: ignore[import]
            JavaInstance as V2Instance,
        )
        from javaobj.v2.beans import (
            JavaString as V2String,
        )
    except ImportError as exc:
        raise JavaObjError("javaobj.v2 is not available; cannot perform v2 → v3 conversion") from exc

    if isinstance(v2_obj, V2String):
        return JavaString(handle=v2_obj.handle, value=v2_obj.value)

    if isinstance(v2_obj, V2Enum):
        cd = _v2_classdesc_to_v3(v2_obj.classdesc)
        constant = JavaString(handle=v2_obj.constant.handle, value=v2_obj.constant.value)
        return JavaEnum(handle=v2_obj.handle, classdesc=cd, constant=constant)

    if isinstance(v2_obj, V2Array):
        cd = _v2_classdesc_to_v3(v2_obj.classdesc)
        data: bytes | list[Any] = (
            bytes(v2_obj.data)
            if v2_obj.field_type and v2_obj.field_type.value == FieldType.BYTE.value
            else list(v2_obj.data)
        )
        return JavaArray(
            handle=v2_obj.handle,
            classdesc=cd,
            element_type=FieldType(v2_obj.field_type.value),
            data=data,
        )

    if isinstance(v2_obj, V2Instance):
        return _v2_instance_to_v3(v2_obj)

    raise JavaObjError(f"Cannot convert v2 object of type {type(v2_obj).__name__!r} to v3")


def _v2_classdesc_to_v3(v2_cd: Any) -> JavaClassDesc:
    """Shallow conversion of a v2 JavaClassDesc to a v3 JavaClassDesc."""
    fields = [
        JavaField(
            type=FieldType(f.type.value),
            name=f.name,
            class_name=f.class_name.value if f.class_name else None,
        )
        for f in (v2_cd.fields or [])
    ]
    return JavaClassDesc(
        handle=v2_cd.handle,
        name=v2_cd.name or "",
        serial_version_uid=v2_cd.serial_version_uid,
        desc_flags=v2_cd.desc_flags,
        fields=fields,
    )


def _v2_instance_to_v3(v2_inst: Any) -> JavaInstance:
    """Shallow conversion of a v2 JavaInstance to a v3 JavaInstance."""
    cd = _v2_classdesc_to_v3(v2_inst.classdesc) if v2_inst.classdesc else None

    v3_inst = JavaInstance()
    v3_inst.handle = v2_inst.handle
    v3_inst.classdesc = cd  # type: ignore[assignment]
    v3_inst.is_exception = getattr(v2_inst, "is_exception", False)

    # Copy field_data with converted keys
    # v2 field_data is {JavaClassDesc: {JavaField: value}}, same nesting as v3
    if cd is not None:
        v3_field_data: dict[JavaClassDesc, dict[JavaField, Any]] = {}
        for v2_cd_key, v2_fields_dict in v2_inst.field_data.items():
            v3_cd_key = _v2_classdesc_to_v3(v2_cd_key)
            v3_fields: dict[JavaField, Any] = {}
            for v2_f, val in v2_fields_dict.items():
                v3_f = JavaField(
                    type=FieldType(v2_f.type.value),
                    name=v2_f.name,
                    class_name=(v2_f.class_name.value if v2_f.class_name else None),
                )
                v3_fields[v3_f] = val
            v3_field_data[v3_cd_key] = v3_fields
        v3_inst.field_data = v3_field_data

    return v3_inst


# ------------------------------------------------------------------------------
# v1 → v3 adapter
# ------------------------------------------------------------------------------


def v1_to_v3(v1_obj: Any) -> ParsedContent:
    """
    Converts a javaobj **v1** top-level object to a v3 equivalent.

    :param v1_obj: A parsed object returned by the top-level
                   :func:`javaobj.load` / :func:`javaobj.loads` (v1 API).
    :return: The v3 equivalent object.
    :raises JavaObjError: If the type cannot be mapped.
    """
    try:
        from javaobj.v1.beans import (
            JavaArray as V1Array,
        )
        from javaobj.v1.beans import (
            JavaEnum as V1Enum,
        )
        from javaobj.v1.beans import (  # type: ignore[import]
            JavaObject,
        )
        from javaobj.v1.beans import (
            JavaString as V1String,
        )
    except ImportError as exc:
        raise JavaObjError("javaobj.v1 is not available; cannot perform v1 → v3 conversion") from exc

    if isinstance(v1_obj, V1String):
        return JavaString(handle=0, value=str(v1_obj))

    if isinstance(v1_obj, V1Enum):
        cd = _v1_classdesc_to_v3(v1_obj.classdesc)
        constant = JavaString(handle=0, value=str(v1_obj.constant))
        return JavaEnum(handle=0, classdesc=cd, constant=constant)

    if isinstance(v1_obj, V1Array):
        return _v1_array_to_v3(v1_obj)

    if isinstance(v1_obj, JavaObject):
        return _v1_object_to_v3(v1_obj)

    raise JavaObjError(f"Cannot convert v1 object of type {type(v1_obj).__name__!r} to v3")


def _v1_classdesc_to_v3(v1_cd: Any) -> JavaClassDesc:
    """Shallow conversion of a v1 JavaClass to a v3 JavaClassDesc."""
    fields = [
        JavaField(
            # fields_types contains full class descriptors like 'Ljava/lang/String;'
            # or single-char primitives like 'B', 'I', etc.  The first character
            # always encodes the FieldType (e.g. 'L' → OBJECT, 'B' → BYTE).
            type=FieldType(ord(str(t)[0])),
            name=n,
        )
        for n, t in zip(
            getattr(v1_cd, "fields_names", []),
            getattr(v1_cd, "fields_types", []),
        )
    ]
    return JavaClassDesc(
        handle=0,
        name=getattr(v1_cd, "name", "") or "",
        serial_version_uid=getattr(v1_cd, "serialVersionUID", 0) or 0,
        desc_flags=getattr(v1_cd, "flags", 0) or 0,
        fields=fields,
    )


def _v1_object_to_v3(v1_obj: Any) -> JavaInstance:
    """Shallow conversion of a v1 JavaObject to a v3 JavaInstance."""
    cd = _v1_classdesc_to_v3(v1_obj.classdesc) if v1_obj.classdesc else None

    v3_inst = JavaInstance()
    v3_inst.handle = 0
    v3_inst.classdesc = cd  # type: ignore[assignment]
    return v3_inst


def _v1_array_to_v3(v1_arr: Any) -> JavaArray:
    """Shallow conversion of a v1 JavaArray to a v3 JavaArray."""
    cd = _v1_classdesc_to_v3(v1_arr.classdesc) if v1_arr.classdesc else None

    raw_data: bytes | list[Any]
    if isinstance(v1_arr, (bytes, bytearray)):
        raw_data = bytes(v1_arr)
    else:
        raw_data = list(v1_arr)

    return JavaArray(
        handle=0,
        classdesc=cd,  # type: ignore[arg-type]
        element_type=FieldType.OBJECT,
        data=raw_data,
    )


# ------------------------------------------------------------------------------
# Convenience mixins for custom transformer classes
# ------------------------------------------------------------------------------


class V2CompatMixin:
    """
    Mixin for v3 transformer subclasses that need a v2-style
    ``load_from_instance(indent=0)`` signature.

    Usage::

        class MyTransformer(V2CompatMixin, JavaInstance):
            HANDLED_CLASSES = "com.example.MyClass"

            def load_from_instance(self, indent: int = 0) -> bool:
                ...
    """

    def load_from_instance(self, indent: int = 0) -> bool:  # type: ignore[override]
        """v2-compatible hook; delegates to the v3 no-argument version."""
        return self._load_from_instance_v3()

    def _load_from_instance_v3(self) -> bool:
        """Override this in subclasses to implement the actual loading."""
        return False


class V1CompatMixin:
    """
    Mixin that adds a ``classdesc`` shim so that v1-style transformer code
    that accesses ``obj.classdesc.name`` works unchanged on v3 instances.
    """

    # No-op: JavaInstance already has a classdesc attribute in v3.
    pass
