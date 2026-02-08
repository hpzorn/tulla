"""Tests for tulla.core.intent — IntentField and extract_intent_fields."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field

from tulla.core.intent import IntentField, extract_intent_fields


# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class _MixedModel(BaseModel):
    """Model with one IntentField and one plain Field."""

    goal: str = IntentField(default="default-goal", description="The user goal")
    revision: int = Field(default=0, description="Internal counter")


class _NoAnnotations(BaseModel):
    """Model with zero IntentField annotations."""

    name: str = Field(default="anon")
    age: int = Field(default=0)


class _AllAnnotated(BaseModel):
    """Model where every field is annotated."""

    alpha: str = IntentField(default="a", description="First")
    beta: int = IntentField(default=1, description="Second")


class _CallerExtra(BaseModel):
    """Model whose IntentField also carries caller-supplied json_schema_extra."""

    tag: str = IntentField(
        default="x",
        description="Tag with extra",
        json_schema_extra={"ui_hint": "dropdown"},
    )


class _RequiredIntentModel(BaseModel):
    """Model with an IntentField that has no default (required)."""

    required_goal: str = IntentField(description="A required intent field")
    optional_note: str = IntentField(default="n/a", description="Optional note")


class _Inner(BaseModel):
    """A nested BaseModel used as a field value."""

    detail: str = "some detail"
    score: int = 10


class _OuterWithNested(BaseModel):
    """Model with a nested BaseModel field annotated as IntentField."""

    nested: _Inner = IntentField(default_factory=_Inner, description="Nested model")
    plain: str = Field(default="ignored")


# ===================================================================
# extract_intent_fields — happy path
# ===================================================================


class TestExtractIntentFieldsHappyPath:
    """extract_intent_fields returns only annotated fields."""

    def test_mixed_model_returns_only_intent_field(self) -> None:
        obj = _MixedModel(goal="ship it", revision=3)
        result = extract_intent_fields(obj)

        assert result == {"goal": "ship it"}
        assert "revision" not in result

    def test_all_annotated_returns_everything(self) -> None:
        obj = _AllAnnotated(alpha="hello", beta=42)
        result = extract_intent_fields(obj)

        assert result == {"alpha": "hello", "beta": 42}

    def test_default_values_are_returned(self) -> None:
        obj = _MixedModel()
        result = extract_intent_fields(obj)

        assert result == {"goal": "default-goal"}

    def test_intent_field_without_default(self) -> None:
        obj = _RequiredIntentModel(required_goal="must provide")
        result = extract_intent_fields(obj)

        assert result == {"required_goal": "must provide", "optional_note": "n/a"}

    def test_nested_basemodel_returned_as_is(self) -> None:
        inner = _Inner(detail="custom", score=99)
        obj = _OuterWithNested(nested=inner)
        result = extract_intent_fields(obj)

        assert result == {"nested": inner}
        assert isinstance(result["nested"], _Inner)
        assert result["nested"].detail == "custom"
        assert result["nested"].score == 99


# ===================================================================
# extract_intent_fields — empty dict cases
# ===================================================================


class TestExtractIntentFieldsEmpty:
    """extract_intent_fields returns empty dict for non-annotated inputs."""

    def test_none_returns_empty(self) -> None:
        assert extract_intent_fields(None) == {}

    def test_non_basemodel_returns_empty(self) -> None:
        assert extract_intent_fields("a string") == {}
        assert extract_intent_fields(42) == {}
        assert extract_intent_fields({"key": "val"}) == {}

    def test_model_with_no_annotations_returns_empty(self) -> None:
        obj = _NoAnnotations(name="test", age=5)
        assert extract_intent_fields(obj) == {}


# ===================================================================
# IntentField — json_schema_extra merging
# ===================================================================


class TestIntentFieldMerging:
    """IntentField correctly merges preserves_intent into json_schema_extra."""

    def test_preserves_intent_is_set(self) -> None:
        info = _MixedModel.model_fields["goal"]
        assert isinstance(info.json_schema_extra, dict)
        assert info.json_schema_extra["preserves_intent"] is True

    def test_plain_field_has_no_preserves_intent(self) -> None:
        info = _MixedModel.model_fields["revision"]
        extra = info.json_schema_extra
        assert extra is None or (
            isinstance(extra, dict) and "preserves_intent" not in extra
        )

    def test_caller_extra_is_preserved(self) -> None:
        info = _CallerExtra.model_fields["tag"]
        assert isinstance(info.json_schema_extra, dict)
        assert info.json_schema_extra["preserves_intent"] is True
        assert info.json_schema_extra["ui_hint"] == "dropdown"

    def test_description_forwarded(self) -> None:
        info = _MixedModel.model_fields["goal"]
        assert info.description == "The user goal"
