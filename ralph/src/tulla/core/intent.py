"""Intent annotation helpers for Pydantic phase outputs.

Provides ``IntentField`` — a thin wrapper around ``pydantic.Field`` that marks
a field as *preserving intent* — and ``extract_intent_fields`` which inspects
a model instance and returns only the fields carrying that marker.

Architecture decision: arch:adr-67-1
"""

from __future__ import annotations

from typing import Any

from pydantic import Field
from pydantic.fields import FieldInfo


def IntentField(  # noqa: N802 – PascalCase mirrors Pydantic's ``Field``
    *,
    default: Any = ...,
    description: str | None = None,
    json_schema_extra: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Create a Pydantic ``Field`` annotated with ``preserves_intent=True``.

    Merges ``{"preserves_intent": True}`` into *json_schema_extra*, preserving
    any additional entries supplied by the caller.  All standard ``Field``
    keyword arguments are forwarded unchanged.
    """
    merged: dict[str, Any] = {**(json_schema_extra or {}), "preserves_intent": True}
    return Field(
        default=default,
        description=description,
        json_schema_extra=merged,
        **kwargs,
    )


def extract_intent_fields(obj: Any) -> dict[str, Any]:
    """Return ``{field_name: value}`` for every intent-annotated field on *obj*.

    Returns an empty dict when *obj* is ``None``, is not a
    ``pydantic.BaseModel``, or has no fields annotated with ``IntentField``.
    """
    if obj is None:
        return {}

    # Guard: must be a Pydantic BaseModel with model_fields on the class
    cls = type(obj)
    model_fields: dict[str, FieldInfo] | None = getattr(cls, "model_fields", None)
    if model_fields is None:
        return {}

    result: dict[str, Any] = {}
    for name, field_info in model_fields.items():
        extra = field_info.json_schema_extra
        if isinstance(extra, dict) and extra.get("preserves_intent") is True:
            result[name] = getattr(obj, name)
    return result
