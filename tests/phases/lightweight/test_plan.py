"""Tests for PlanPhase — Claude-invoked tactical planning.

# @pattern:PortsAndAdapters -- Tests use MockClaudeAdapter injected via claude_port config key, no real subprocess
# @principle:FailSafeRouting -- Tests verify that missing optional fields default safely (empty risk_notes, empty lists)
# @pattern:LooseCoupling -- Tests exercise PlanPhase through the Phase.execute() public API, not internal methods
# @principle:DependencyInversion -- Tests depend on ClaudePort abstraction, never on concrete subprocess adapter

Verification criteria (prd:req-53-3-3):
- Prompt construction includes conformance data (violations, patterns, conformance_status).
- JSON parsing from mock Claude response (output_json, output_text, markdown-fenced).
- Handling of incomplete Claude responses (missing optional fields default safely).
- Mock Claude port (following the pattern from adapters/claude_mock.py) used throughout.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import PhaseContext, PhaseStatus
from tulla.phases.lightweight.models import ContextScanOutput, PlanOutput
from tulla.phases.lightweight.plan import PlanPhase
from tulla.ports.claude import ClaudePort, ClaudeRequest, ClaudeResult


# ---------------------------------------------------------------------------
# Mock Claude port
# ---------------------------------------------------------------------------


class MockClaudePort(ClaudePort):
    """A mock ClaudePort that returns a canned JSON response."""

    def __init__(self, response_json: dict[str, Any]) -> None:
        self._response_json = response_json

    def run(self, request: ClaudeRequest) -> ClaudeResult:
        return ClaudeResult(
            exit_code=0,
            output_text=json.dumps(self._response_json),
            output_json=self._response_json,
            cost_usd=0.01,
            duration_seconds=1.0,
            timed_out=False,
        )


class MockClaudePortTextOnly(ClaudePort):
    """A mock ClaudePort that returns JSON as plain text (no output_json)."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    def run(self, request: ClaudeRequest) -> ClaudeResult:
        return ClaudeResult(
            exit_code=0,
            output_text=self._response_text,
            output_json=None,
            cost_usd=0.01,
            duration_seconds=1.0,
            timed_out=False,
        )


# ---------------------------------------------------------------------------
# Canned responses
# ---------------------------------------------------------------------------

CANNED_PLAN = {
    "plan_summary": "Fix import violation in core/bad.py by moving the import to the outer layer",
    "plan_steps": [
        "Identify the circular import in core/bad.py",
        "Move the tulla.cli import to a local scope",
        "Add a facade in the outer layer for the needed functionality",
        "Update tests to reflect the new import structure",
    ],
    "files_to_modify": ["src/tulla/core/bad.py", "src/tulla/cli.py", "tests/test_bad.py"],
    "risk_notes": "Moving imports may break downstream consumers; run full test suite after change.",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def phase() -> PlanPhase:
    return PlanPhase()


def _make_ctx(
    tmp_path: Path,
    claude_port: ClaudePort,
    prev_output: Any = None,
    **extra: Any,
) -> PhaseContext:
    """Build a PhaseContext with a mock Claude port and optional prev_output."""
    config: dict[str, Any] = {"claude_port": claude_port, **extra}
    if prev_output is not None:
        config["prev_output"] = prev_output
    return PhaseContext(idea_id="test-idea", work_dir=tmp_path, config=config)


def _make_context_scan_output(**overrides: Any) -> ContextScanOutput:
    """Create a ContextScanOutput with sensible defaults."""
    defaults: dict[str, Any] = {
        "violations": [{"file": "core/bad.py", "import": "tulla.cli", "rule": "inner-to-outer"}],
        "violation_report": "Violation Report\n- core/bad.py imports tulla.cli (inner -> outer)",
        "patterns": ["PortsAndAdapters"],
        "principles": ["DependencyInversion"],
        "conformance_status": "structural-only:violations-found",
        "quality_focus": "isaqb:Maintainability",
    }
    defaults.update(overrides)
    return ContextScanOutput(**defaults)


# ---------------------------------------------------------------------------
# Tests: successful execution with mock Claude
# ---------------------------------------------------------------------------


class TestSuccessfulExecution:
    """Verify execute() produces PhaseResult[PlanOutput] with SUCCESS."""

    def test_execute_with_canned_json(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Mock Claude returns canned JSON -> SUCCESS with correctly parsed fields."""
        port = MockClaudePort(CANNED_PLAN)
        prev = _make_context_scan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, PlanOutput)
        assert result.data.plan_summary == CANNED_PLAN["plan_summary"]
        assert result.data.plan_steps == CANNED_PLAN["plan_steps"]
        assert result.data.files_to_modify == CANNED_PLAN["files_to_modify"]
        assert result.data.risk_notes == CANNED_PLAN["risk_notes"]

    def test_execute_with_text_only_response(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Mock Claude returns JSON as text only -> SUCCESS with parsed fields."""
        port = MockClaudePortTextOnly(json.dumps(CANNED_PLAN))
        prev = _make_context_scan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, PlanOutput)
        assert result.data.plan_summary == CANNED_PLAN["plan_summary"]
        assert result.data.plan_steps == CANNED_PLAN["plan_steps"]

    def test_execute_with_markdown_fenced_json(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Mock Claude returns JSON wrapped in markdown code fences -> SUCCESS."""
        fenced = f"```json\n{json.dumps(CANNED_PLAN, indent=2)}\n```"
        port = MockClaudePortTextOnly(fenced)
        prev = _make_context_scan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, PlanOutput)
        assert result.data.plan_summary == CANNED_PLAN["plan_summary"]

    def test_execute_records_cost_metadata(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Cost metadata from ClaudeResult is captured in PhaseResult."""
        port = MockClaudePort(CANNED_PLAN)
        prev = _make_context_scan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.metadata.get("cost_usd") == 0.01


# ---------------------------------------------------------------------------
# Tests: default values for incomplete responses
# ---------------------------------------------------------------------------


class TestDefaults:
    """Verify reasonable defaults when Claude's response is incomplete."""

    def test_missing_risk_notes_defaults_to_empty(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Missing risk_notes -> defaults to empty string."""
        partial = {
            "plan_summary": "Minimal plan",
            "plan_steps": ["Step 1"],
            "files_to_modify": ["file.py"],
        }
        port = MockClaudePort(partial)
        prev = _make_context_scan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, PlanOutput)
        assert result.data.risk_notes == ""

    def test_missing_fields_default_to_empty(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Missing plan_steps and files_to_modify -> default to empty lists."""
        minimal = {"plan_summary": "Just a summary"}
        port = MockClaudePort(minimal)
        prev = _make_context_scan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, PlanOutput)
        assert result.data.plan_steps == []
        assert result.data.files_to_modify == []
        assert result.data.risk_notes == ""

    def test_completely_empty_json_defaults_all_fields(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Empty JSON object -> all fields default to empty values."""
        port = MockClaudePort({})
        prev = _make_context_scan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, PlanOutput)
        assert result.data.plan_summary == ""
        assert result.data.plan_steps == []
        assert result.data.files_to_modify == []
        assert result.data.risk_notes == ""


# ---------------------------------------------------------------------------
# Tests: prompt construction
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    """Verify build_prompt() includes conformance context."""

    def test_prompt_includes_violation_report(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Prompt includes the violation report from ContextScanOutput."""
        prev = _make_context_scan_output()
        port = MockClaudePort(CANNED_PLAN)
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        prompt = phase.build_prompt(ctx)

        assert "Violation Report" in prompt
        assert "core/bad.py" in prompt

    def test_prompt_includes_patterns(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Prompt includes detected patterns."""
        prev = _make_context_scan_output(patterns=["Singleton", "Observer"])
        port = MockClaudePort(CANNED_PLAN)
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        prompt = phase.build_prompt(ctx)

        assert "Singleton" in prompt
        assert "Observer" in prompt

    def test_prompt_includes_change_description(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Prompt includes the change description from config."""
        prev = _make_context_scan_output()
        port = MockClaudePort(CANNED_PLAN)
        ctx = _make_ctx(
            tmp_path, port, prev_output=prev,
            change_description="Fix the import cycle in core module",
        )

        prompt = phase.build_prompt(ctx)

        assert "Fix the import cycle in core module" in prompt

    def test_prompt_includes_conformance_status(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Prompt includes the conformance_status from ContextScanOutput."""
        prev = _make_context_scan_output(
            conformance_status="structural-only:violations-found",
        )
        port = MockClaudePort(CANNED_PLAN)
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        prompt = phase.build_prompt(ctx)

        assert "structural-only:violations-found" in prompt

    def test_prompt_includes_affected_files(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Prompt includes affected_files from config."""
        prev = _make_context_scan_output()
        port = MockClaudePort(CANNED_PLAN)
        ctx = _make_ctx(
            tmp_path, port, prev_output=prev,
            affected_files=["src/core.py", "tests/test_core.py"],
        )

        prompt = phase.build_prompt(ctx)

        assert "src/core.py" in prompt
        assert "tests/test_core.py" in prompt

    def test_prompt_no_violations_shows_clean_message(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """When there are no violations, prompt says 'No violations detected'."""
        prev = _make_context_scan_output(
            violations=[],
            violation_report="",
            conformance_status="structural-only:clean",
        )
        port = MockClaudePort(CANNED_PLAN)
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        prompt = phase.build_prompt(ctx)

        assert "No violations detected" in prompt

    def test_prompt_includes_upstream_facts(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Prompt includes upstream ontology facts when available."""
        prev = _make_context_scan_output()
        port = MockClaudePort(CANNED_PLAN)
        facts = [{"predicate": "hasPattern", "object": "PortsAndAdapters"}]
        ctx = _make_ctx(
            tmp_path, port, prev_output=prev,
            upstream_facts=facts,
        )

        prompt = phase.build_prompt(ctx)

        assert "Upstream Ontology Facts" in prompt
        assert "PortsAndAdapters" in prompt

    def test_prompt_omits_upstream_section_when_empty(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Prompt omits the upstream facts section when no facts are present."""
        prev = _make_context_scan_output()
        port = MockClaudePort(CANNED_PLAN)
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        prompt = phase.build_prompt(ctx)

        assert "Upstream Ontology Facts" not in prompt

    def test_prompt_includes_idea_id(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Prompt includes the idea_id from PhaseContext."""
        prev = _make_context_scan_output()
        port = MockClaudePort(CANNED_PLAN)
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        prompt = phase.build_prompt(ctx)

        assert "test-idea" in prompt

    def test_prompt_without_prev_output(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Prompt can be built without prev_output (graceful degradation)."""
        port = MockClaudePort(CANNED_PLAN)
        ctx = _make_ctx(tmp_path, port)

        prompt = phase.build_prompt(ctx)

        assert "No violations detected" in prompt

    def test_prompt_with_dict_prev_output(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Prompt works with prev_output as a plain dict."""
        prev_dict = {
            "violations": [],
            "violation_report": "No violations",
            "patterns": ["Strategy"],
            "principles": [],
            "conformance_status": "structural-only:clean",
            "quality_focus": "isaqb:Maintainability",
        }
        port = MockClaudePort(CANNED_PLAN)
        ctx = _make_ctx(tmp_path, port, prev_output=prev_dict)

        prompt = phase.build_prompt(ctx)

        assert "Strategy" in prompt


# ---------------------------------------------------------------------------
# Tests: get_tools returns empty
# ---------------------------------------------------------------------------


class TestGetTools:
    """Verify get_tools() returns empty list (analysis-only phase)."""

    def test_get_tools_returns_empty(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        port = MockClaudePort(CANNED_PLAN)
        ctx = _make_ctx(tmp_path, port)
        assert phase.get_tools(ctx) == []


# ---------------------------------------------------------------------------
# Tests: parse_output error handling
# ---------------------------------------------------------------------------


class TestParseOutputErrors:
    """Verify parse_output raises ParseError for unparseable responses."""

    def test_unparseable_response_fails(
        self, phase: PlanPhase, tmp_path: Path
    ) -> None:
        """Non-JSON response -> FAILURE status."""
        port = MockClaudePortTextOnly("This is not JSON at all")
        prev = _make_context_scan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.FAILURE
        assert result.error is not None
        assert "parsing" in result.error.lower() or "parse" in result.error.lower()


# ---------------------------------------------------------------------------
# Tests: phase metadata
# ---------------------------------------------------------------------------


class TestPhaseMetadata:
    """Verify basic phase attributes."""

    def test_phase_id(self, phase: PlanPhase) -> None:
        assert phase.phase_id == "plan"

    def test_timeout(self, phase: PlanPhase) -> None:
        assert phase.timeout_s == 300.0
