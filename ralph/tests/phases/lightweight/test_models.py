"""Tests for lightweight pipeline phase output models.

# @pattern:SeparationOfConcerns -- Each test class isolates one model's behaviour
# @principle:DependencyInversion -- Tests depend on the public IntentField API, not json_schema_extra internals
# @quality:Testability -- Fixtures decouple test data from assertion logic

Verification criteria (prd:req-53-1-3):
- Construction of each model with valid data.
- Validation rejection of invalid change_type values (if constrained by Literal).
- extract_intent_fields() returns correct field count for LightweightTraceResult.
- Only LightweightTraceResult has IntentField-annotated fields; the other four
  models return an empty dict from extract_intent_fields().
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tulla.core.intent import extract_intent_fields
from tulla.phases.lightweight.models import (
    ContextScanOutput,
    ExecuteOutput,
    IntakeOutput,
    LightweightTraceResult,
    PlanOutput,
)


# ---------------------------------------------------------------------------
# Fixtures: valid data for each model
# ---------------------------------------------------------------------------

@pytest.fixture()
def intake_data() -> dict:
    return {
        "change_type": "bugfix",
        "description": "Fix null pointer in parser",
        "affected_files": ["src/parser.py", "tests/test_parser.py"],
        "scope": "single-package",
        "lightweight_eligible": True,
    }


@pytest.fixture()
def context_scan_data() -> dict:
    return {
        "violations": [{"rule": "no-unused-vars", "file": "src/parser.py"}],
        "violation_report": "1 violation found",
        "patterns": ["singleton", "factory"],
        "principles": ["SRP", "DIP"],
        "conformance_status": "structural-only:pass",
        "quality_focus": "isaqb:FunctionalCorrectness",
    }


@pytest.fixture()
def plan_data() -> dict:
    return {
        "plan_summary": "Fix null check before access",
        "plan_steps": ["Add guard clause", "Update tests"],
        "files_to_modify": ["src/parser.py"],
        "risk_notes": "Low risk, isolated change",
    }


@pytest.fixture()
def execute_data() -> dict:
    return {
        "changes_summary": "Added null guard in parse()",
        "files_modified": ["src/parser.py"],
        "commit_ref": "abc1234",
        "execution_notes": "Clean apply, no conflicts",
    }


@pytest.fixture()
def trace_required_only() -> dict:
    """Minimal LightweightTraceResult — only required fields."""
    return {
        "change_type": "bugfix",
        "affected_files": "src/parser.py,tests/test_parser.py",
        "conformance_assertion": "structural-only:pass",
        "commit_ref": "abc1234",
        "change_summary": "Fix null pointer in parser",
        "timestamp": "2025-01-15T10:30:00Z",
    }


@pytest.fixture()
def trace_all_fields(trace_required_only: dict) -> dict:
    """Full LightweightTraceResult — all 9 fields populated."""
    return {
        **trace_required_only,
        "issue_ref": "PROJ-42",
        "sprint_id": "sprint-7",
        "story_points": "3",
    }


# ---------------------------------------------------------------------------
# Tests: model instantiation
# ---------------------------------------------------------------------------

class TestIntakeOutput:
    def test_instantiation(self, intake_data: dict) -> None:
        model = IntakeOutput(**intake_data)
        assert model.change_type == "bugfix"
        assert model.description == "Fix null pointer in parser"
        assert model.affected_files == ["src/parser.py", "tests/test_parser.py"]
        assert model.scope == "single-package"
        assert model.lightweight_eligible is True

    def test_change_type_accepts_any_string(self, intake_data: dict) -> None:
        """change_type is str (not Literal-constrained); any string is valid."""
        data = {**intake_data, "change_type": "unknown-category"}
        model = IntakeOutput(**data)
        assert model.change_type == "unknown-category"

    def test_rejects_missing_required_fields(self) -> None:
        """Omitting a required field raises ValidationError."""
        with pytest.raises(ValidationError):
            IntakeOutput()  # type: ignore[call-arg]

    def test_no_intent_fields(self, intake_data: dict) -> None:
        model = IntakeOutput(**intake_data)
        assert extract_intent_fields(model) == {}


class TestContextScanOutput:
    def test_instantiation(self, context_scan_data: dict) -> None:
        model = ContextScanOutput(**context_scan_data)
        assert model.conformance_status == "structural-only:pass"
        assert len(model.violations) == 1
        assert model.patterns == ["singleton", "factory"]
        assert model.principles == ["SRP", "DIP"]
        assert model.quality_focus == "isaqb:FunctionalCorrectness"

    def test_rejects_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            ContextScanOutput()  # type: ignore[call-arg]

    def test_no_intent_fields(self, context_scan_data: dict) -> None:
        model = ContextScanOutput(**context_scan_data)
        assert extract_intent_fields(model) == {}


class TestPlanOutput:
    def test_instantiation(self, plan_data: dict) -> None:
        model = PlanOutput(**plan_data)
        assert model.plan_summary == "Fix null check before access"
        assert len(model.plan_steps) == 2
        assert model.files_to_modify == ["src/parser.py"]
        assert model.risk_notes == "Low risk, isolated change"

    def test_rejects_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            PlanOutput()  # type: ignore[call-arg]

    def test_no_intent_fields(self, plan_data: dict) -> None:
        model = PlanOutput(**plan_data)
        assert extract_intent_fields(model) == {}


class TestExecuteOutput:
    def test_instantiation(self, execute_data: dict) -> None:
        model = ExecuteOutput(**execute_data)
        assert model.changes_summary == "Added null guard in parse()"
        assert model.files_modified == ["src/parser.py"]
        assert model.commit_ref == "abc1234"
        assert model.execution_notes == "Clean apply, no conflicts"

    def test_rejects_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            ExecuteOutput()  # type: ignore[call-arg]

    def test_no_intent_fields(self, execute_data: dict) -> None:
        model = ExecuteOutput(**execute_data)
        assert extract_intent_fields(model) == {}


# ---------------------------------------------------------------------------
# Tests: LightweightTraceResult + IntentField
# ---------------------------------------------------------------------------

class TestLightweightTraceResult:
    def test_instantiation_required_only(self, trace_required_only: dict) -> None:
        model = LightweightTraceResult(**trace_required_only)
        assert model.change_type == "bugfix"
        assert model.affected_files == "src/parser.py,tests/test_parser.py"
        assert model.conformance_assertion == "structural-only:pass"
        assert model.commit_ref == "abc1234"
        assert model.change_summary == "Fix null pointer in parser"
        assert model.timestamp == "2025-01-15T10:30:00Z"
        # Optional fields default to None
        assert model.issue_ref is None
        assert model.sprint_id is None
        assert model.story_points is None

    def test_instantiation_all_fields(self, trace_all_fields: dict) -> None:
        model = LightweightTraceResult(**trace_all_fields)
        assert model.issue_ref == "PROJ-42"
        assert model.sprint_id == "sprint-7"
        assert model.story_points == "3"

    def test_change_type_accepts_any_string(
        self, trace_required_only: dict
    ) -> None:
        """change_type is str (not Literal-constrained); any string is valid."""
        data = {**trace_required_only, "change_type": "arbitrary-value"}
        model = LightweightTraceResult(**data)
        assert model.change_type == "arbitrary-value"

    def test_rejects_missing_required_fields(self) -> None:
        """Omitting required IntentFields raises ValidationError."""
        with pytest.raises(ValidationError):
            LightweightTraceResult()  # type: ignore[call-arg]

    def test_extract_intent_6_keys_when_optionals_none(
        self, trace_required_only: dict
    ) -> None:
        """extract_intent_fields() returns exactly 6 keys when optional
        IntentFields are None."""
        model = LightweightTraceResult(**trace_required_only)
        intent = extract_intent_fields(model)
        # Filter out None values — only non-None intent fields count
        non_none = {k: v for k, v in intent.items() if v is not None}
        assert len(non_none) == 6
        assert set(non_none.keys()) == {
            "change_type",
            "affected_files",
            "conformance_assertion",
            "commit_ref",
            "change_summary",
            "timestamp",
        }

    def test_extract_intent_9_keys_when_all_populated(
        self, trace_all_fields: dict
    ) -> None:
        """extract_intent_fields() returns 9 keys when all optional
        IntentFields are populated."""
        model = LightweightTraceResult(**trace_all_fields)
        intent = extract_intent_fields(model)
        non_none = {k: v for k, v in intent.items() if v is not None}
        assert len(non_none) == 9
        assert set(non_none.keys()) == {
            "change_type",
            "affected_files",
            "conformance_assertion",
            "commit_ref",
            "change_summary",
            "timestamp",
            "issue_ref",
            "sprint_id",
            "story_points",
        }

    def test_all_nine_fields_are_intent_annotated(self) -> None:
        """All 9 fields on LightweightTraceResult carry the
        preserves_intent marker."""
        fields = LightweightTraceResult.model_fields
        intent_fields = [
            name
            for name, info in fields.items()
            if isinstance(info.json_schema_extra, dict)
            and info.json_schema_extra.get("preserves_intent") is True
        ]
        assert len(intent_fields) == 9

    def test_intent_field_values_correct(self, trace_all_fields: dict) -> None:
        """Extracted intent field values match the model's actual values."""
        model = LightweightTraceResult(**trace_all_fields)
        intent = extract_intent_fields(model)
        assert intent["change_type"] == "bugfix"
        assert intent["commit_ref"] == "abc1234"
        assert intent["issue_ref"] == "PROJ-42"
        assert intent["story_points"] == "3"
