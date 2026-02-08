"""Tests for TracePhase — assembles the final trace model from upstream outputs.

# @pattern:PortsAndAdapters -- TracePhase overrides run_claude() for local computation; tests verify port-boundary data contracts via mock upstream outputs
# @principle:SeparationOfConcerns -- Tests validate pure assembly logic in isolation from KG persistence and pipeline wiring
# @pattern:InformationHiding -- Tests interact only with public execute() and extract_intent_fields(); internal _get_attr_or_key is tested indirectly
# @principle:DependencyInversion -- Mock upstream outputs (IntakeOutput, ContextScanOutput, ExecuteOutput) injected via PhaseContext.config dict

Verification criteria (prd:req-53-2-4):
- Assembly from mock upstream outputs: verify all 6 required fields populated.
- Correct ISO 8601 timestamp format with timezone.
- Optional field propagation when present and absent.
- extract_intent_fields() returns the expected 9-field count.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from tulla.core.intent import extract_intent_fields
from tulla.core.phase import PhaseContext, PhaseStatus
from tulla.phases.lightweight.models import (
    ContextScanOutput,
    ExecuteOutput,
    IntakeOutput,
    LightweightTraceResult,
)
from tulla.phases.lightweight.trace import TracePhase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def phase() -> TracePhase:
    return TracePhase()


def _make_intake_output(**overrides: Any) -> IntakeOutput:
    """Build an IntakeOutput with sensible defaults."""
    defaults: dict[str, Any] = {
        "change_type": "bugfix",
        "description": "Fix a bug in the parser",
        "affected_files": ["src/parser.py"],
        "scope": "single-package",
        "lightweight_eligible": True,
    }
    defaults.update(overrides)
    return IntakeOutput(**defaults)


def _make_context_scan_output(**overrides: Any) -> ContextScanOutput:
    """Build a ContextScanOutput with sensible defaults."""
    defaults: dict[str, Any] = {
        "violations": [],
        "violation_report": "No violations",
        "patterns": [],
        "principles": [],
        "conformance_status": "structural-only:clean",
        "quality_focus": "isaqb:Maintainability",
    }
    defaults.update(overrides)
    return ContextScanOutput(**defaults)


def _make_execute_output(**overrides: Any) -> ExecuteOutput:
    """Build an ExecuteOutput with sensible defaults."""
    defaults: dict[str, Any] = {
        "changes_summary": "Fixed parser edge case for nested brackets",
        "files_modified": ["src/parser.py", "tests/test_parser.py"],
        "commit_ref": "abc1234",
        "execution_notes": "All tests pass",
    }
    defaults.update(overrides)
    return ExecuteOutput(**defaults)


def _make_ctx(
    tmp_path: Path,
    intake_output: IntakeOutput | dict | None = None,
    context_scan_output: ContextScanOutput | dict | None = None,
    prev_output: ExecuteOutput | dict | None = None,
    **extra: Any,
) -> PhaseContext:
    """Build a PhaseContext with upstream outputs for TracePhase."""
    if intake_output is None:
        intake_output = _make_intake_output()
    if context_scan_output is None:
        context_scan_output = _make_context_scan_output()
    if prev_output is None:
        prev_output = _make_execute_output()

    config: dict[str, Any] = {
        "prev_output": prev_output,
        "intake_output": intake_output,
        "context_scan_output": context_scan_output,
        **extra,
    }
    return PhaseContext(idea_id="test-idea", work_dir=tmp_path, config=config)


# ---------------------------------------------------------------------------
# Tests: all 6 required fields populated
# ---------------------------------------------------------------------------


class TestRequiredFieldsPopulated:
    """Verify that all 6 required fields are populated from upstream outputs."""

    def test_all_required_fields_present(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """All 6 required fields are populated from upstream mock outputs."""
        ctx = _make_ctx(tmp_path)
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, LightweightTraceResult)

        data = result.data
        assert data.change_type == "bugfix"
        assert data.affected_files == "src/parser.py,tests/test_parser.py"
        assert data.conformance_assertion == "structural-only:clean"
        assert data.commit_ref == "abc1234"
        assert data.change_summary == "Fixed parser edge case for nested brackets"
        assert data.timestamp  # non-empty

    def test_change_type_from_intake(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """change_type is mapped from IntakeOutput."""
        intake = _make_intake_output(change_type="feature")
        ctx = _make_ctx(tmp_path, intake_output=intake)
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.change_type == "feature"

    def test_affected_files_comma_separated(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """affected_files is a comma-separated string from ExecuteOutput.files_modified."""
        execute = _make_execute_output(
            files_modified=["a.py", "b.py", "c.py"]
        )
        ctx = _make_ctx(tmp_path, prev_output=execute)
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.affected_files == "a.py,b.py,c.py"

    def test_conformance_from_context_scan(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """conformance_assertion is mapped from ContextScanOutput.conformance_status."""
        scan = _make_context_scan_output(
            conformance_status="structural-only:violations-found"
        )
        ctx = _make_ctx(tmp_path, context_scan_output=scan)
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.conformance_assertion == "structural-only:violations-found"

    def test_commit_ref_from_execute(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """commit_ref is mapped from ExecuteOutput."""
        execute = _make_execute_output(commit_ref="deadbeef")
        ctx = _make_ctx(tmp_path, prev_output=execute)
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.commit_ref == "deadbeef"

    def test_change_summary_from_execute(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """change_summary is mapped from ExecuteOutput.changes_summary."""
        execute = _make_execute_output(changes_summary="Refactored module X")
        ctx = _make_ctx(tmp_path, prev_output=execute)
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.change_summary == "Refactored module X"


# ---------------------------------------------------------------------------
# Tests: timestamp format
# ---------------------------------------------------------------------------


class TestTimestampFormat:
    """Verify timestamp is current UTC in ISO 8601 format."""

    def test_timestamp_is_iso_8601(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """timestamp is a valid ISO 8601 string."""
        ctx = _make_ctx(tmp_path)
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None

        # Verify it parses as ISO 8601
        parsed = datetime.fromisoformat(result.data.timestamp)
        assert parsed.tzinfo is not None  # has timezone info

    def test_timestamp_is_recent_utc(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """timestamp is close to current UTC time."""
        before = datetime.now(timezone.utc)
        ctx = _make_ctx(tmp_path)
        result = phase.execute(ctx)
        after = datetime.now(timezone.utc)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None

        parsed = datetime.fromisoformat(result.data.timestamp)
        assert before <= parsed <= after


# ---------------------------------------------------------------------------
# Tests: extract_intent_fields() count
# ---------------------------------------------------------------------------


class TestExtractIntentFields:
    """Verify extract_intent_fields() returns the expected field count."""

    def test_all_nine_intent_fields_present(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """All 9 IntentField-annotated fields are returned by extract_intent_fields()."""
        ctx = _make_ctx(tmp_path)
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None

        intent = extract_intent_fields(result.data)
        # All 9 IntentField-annotated fields are always returned
        assert len(intent) == 9
        assert "change_type" in intent
        assert "affected_files" in intent
        assert "conformance_assertion" in intent
        assert "commit_ref" in intent
        assert "change_summary" in intent
        assert "timestamp" in intent
        assert "issue_ref" in intent
        assert "sprint_id" in intent
        assert "story_points" in intent

    def test_optional_fields_none_when_absent(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """Optional fields default to None when not provided in ctx.config."""
        ctx = _make_ctx(tmp_path)
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None

        assert result.data.issue_ref is None
        assert result.data.sprint_id is None
        assert result.data.story_points is None

    def test_optional_fields_populated_when_provided(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """Optional fields are populated when provided in ctx.config."""
        ctx = _make_ctx(
            tmp_path,
            issue_ref="PROJ-42",
            sprint_id="sprint-7",
            story_points="3",
        )
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None

        intent = extract_intent_fields(result.data)
        assert len(intent) == 9
        assert intent["issue_ref"] == "PROJ-42"
        assert intent["sprint_id"] == "sprint-7"
        assert intent["story_points"] == "3"

    def test_partial_optionals(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """Partial optionals: only issue_ref provided."""
        ctx = _make_ctx(tmp_path, issue_ref="BUG-99")
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None

        assert result.data.issue_ref == "BUG-99"
        assert result.data.sprint_id is None
        assert result.data.story_points is None


# ---------------------------------------------------------------------------
# Tests: upstream outputs as dicts
# ---------------------------------------------------------------------------


class TestDictUpstreamOutputs:
    """Verify that upstream outputs work when passed as plain dicts."""

    def test_dict_upstream_outputs(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """All upstream outputs as dicts should work identically to models."""
        intake_dict = {
            "change_type": "enhancement",
            "description": "Enhance logging",
            "affected_files": ["src/log.py"],
            "scope": "single-package",
            "lightweight_eligible": True,
        }
        scan_dict = {
            "violations": [],
            "violation_report": "",
            "patterns": [],
            "principles": [],
            "conformance_status": "structural-only:clean",
            "quality_focus": "",
        }
        execute_dict = {
            "changes_summary": "Added structured logging",
            "files_modified": ["src/log.py"],
            "commit_ref": "cafe123",
            "execution_notes": "",
        }
        ctx = _make_ctx(
            tmp_path,
            intake_output=intake_dict,
            context_scan_output=scan_dict,
            prev_output=execute_dict,
        )
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.change_type == "enhancement"
        assert result.data.affected_files == "src/log.py"
        assert result.data.conformance_assertion == "structural-only:clean"
        assert result.data.commit_ref == "cafe123"
        assert result.data.change_summary == "Added structured logging"


# ---------------------------------------------------------------------------
# Tests: missing upstream outputs
# ---------------------------------------------------------------------------


class TestMissingUpstreamOutputs:
    """Verify graceful handling when upstream outputs are missing."""

    def test_no_upstream_outputs(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        """Missing upstream outputs produce empty-string defaults."""
        ctx = PhaseContext(
            idea_id="test-idea", work_dir=tmp_path, config={}
        )
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.change_type == ""
        assert result.data.affected_files == ""
        assert result.data.conformance_assertion == ""
        assert result.data.commit_ref == ""
        assert result.data.change_summary == ""
        assert result.data.timestamp  # still populated


# ---------------------------------------------------------------------------
# Tests: phase metadata
# ---------------------------------------------------------------------------


class TestPhaseMetadata:
    """Verify basic phase attributes."""

    def test_phase_id(self, phase: TracePhase) -> None:
        assert phase.phase_id == "trace"

    def test_build_prompt_returns_empty(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        ctx = _make_ctx(tmp_path)
        assert phase.build_prompt(ctx) == ""

    def test_get_tools_returns_empty(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        ctx = _make_ctx(tmp_path)
        assert phase.get_tools(ctx) == []

    def test_parse_output_wraps_dict(
        self, phase: TracePhase, tmp_path: Path
    ) -> None:
        ctx = _make_ctx(tmp_path)
        raw = {
            "change_type": "chore",
            "affected_files": "a.py",
            "conformance_assertion": "structural-only:clean",
            "commit_ref": "1234567",
            "change_summary": "Updated deps",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "issue_ref": None,
            "sprint_id": None,
            "story_points": None,
        }
        output = phase.parse_output(ctx, raw)
        assert isinstance(output, LightweightTraceResult)
        assert output.change_type == "chore"
        assert output.commit_ref == "1234567"
