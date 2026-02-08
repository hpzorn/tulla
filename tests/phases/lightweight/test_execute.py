"""Tests for ExecutePhase -- Claude-invoked execution.

# @pattern:PortsAndAdapters -- Tests use MockClaudePort injected via claude_port config key, no real subprocess
# @principle:FailSafeRouting -- Tests verify dry-run mode produces empty commit_ref and missing fields default safely
# @pattern:LooseCoupling -- Tests exercise ExecutePhase through the Phase.execute() public API, not internal methods
# @principle:DependencyInversion -- Tests depend on ClaudePort abstraction, never on concrete subprocess adapter

Verification criteria (prd:req-53-3-3):
- Prompt includes guard-rail instructions (only modify listed files, no new deps, follow conventions).
- Tool list includes file and bash tools (Read, Write, Edit, Glob, Grep, Bash).
- Parsing of commit SHA and file list from mock Claude response.
- Dry-run mode produces empty commit_ref.
- Mock Claude port (following the pattern from adapters/claude_mock.py) used throughout.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import PhaseContext, PhaseStatus
from tulla.phases.lightweight.execute import ExecutePhase
from tulla.phases.lightweight.models import ExecuteOutput, PlanOutput
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
            cost_usd=0.02,
            duration_seconds=5.0,
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
            cost_usd=0.02,
            duration_seconds=5.0,
            timed_out=False,
        )


# ---------------------------------------------------------------------------
# Canned responses
# ---------------------------------------------------------------------------

CANNED_EXECUTE = {
    "changes_summary": "Fixed import cycle by moving tulla.cli import to local scope in core/bad.py",
    "files_modified": ["src/tulla/core/bad.py", "src/tulla/cli.py"],
    "commit_ref": "abc1234def5678",
    "execution_notes": "All tests passing after change.",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def phase() -> ExecutePhase:
    return ExecutePhase()


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


def _make_plan_output(**overrides: Any) -> PlanOutput:
    """Create a PlanOutput with sensible defaults."""
    defaults: dict[str, Any] = {
        "plan_summary": "Fix import violation in core/bad.py by moving the import to the outer layer",
        "plan_steps": [
            "Identify the circular import in core/bad.py",
            "Move the tulla.cli import to a local scope",
            "Update tests to reflect the new import structure",
        ],
        "files_to_modify": ["src/tulla/core/bad.py", "src/tulla/cli.py"],
        "risk_notes": "Moving imports may break downstream consumers.",
    }
    defaults.update(overrides)
    return PlanOutput(**defaults)


# ---------------------------------------------------------------------------
# Tests: successful execution with mock Claude
# ---------------------------------------------------------------------------


class TestSuccessfulExecution:
    """Verify execute() produces PhaseResult[ExecuteOutput] with SUCCESS."""

    def test_execute_with_canned_json(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Mock Claude returns canned JSON -> SUCCESS with correctly parsed fields."""
        port = MockClaudePort(CANNED_EXECUTE)
        prev = _make_plan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, ExecuteOutput)
        assert result.data.changes_summary == CANNED_EXECUTE["changes_summary"]
        assert result.data.files_modified == CANNED_EXECUTE["files_modified"]
        assert result.data.commit_ref == CANNED_EXECUTE["commit_ref"]
        assert result.data.execution_notes == CANNED_EXECUTE["execution_notes"]

    def test_execute_with_text_only_response(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Mock Claude returns JSON as text only -> SUCCESS with parsed fields."""
        port = MockClaudePortTextOnly(json.dumps(CANNED_EXECUTE))
        prev = _make_plan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, ExecuteOutput)
        assert result.data.commit_ref == CANNED_EXECUTE["commit_ref"]
        assert result.data.files_modified == CANNED_EXECUTE["files_modified"]

    def test_execute_with_markdown_fenced_json(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Mock Claude returns JSON wrapped in markdown code fences -> SUCCESS."""
        fenced = f"```json\n{json.dumps(CANNED_EXECUTE, indent=2)}\n```"
        port = MockClaudePortTextOnly(fenced)
        prev = _make_plan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, ExecuteOutput)
        assert result.data.commit_ref == CANNED_EXECUTE["commit_ref"]

    def test_execute_records_cost_metadata(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Cost metadata from ClaudeResult is captured in PhaseResult."""
        port = MockClaudePort(CANNED_EXECUTE)
        prev = _make_plan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.metadata.get("cost_usd") == 0.02


# ---------------------------------------------------------------------------
# Tests: default values for incomplete responses
# ---------------------------------------------------------------------------


class TestDefaults:
    """Verify reasonable defaults when Claude's response is incomplete."""

    def test_empty_commit_ref_for_dry_run(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Missing commit_ref -> defaults to empty string (dry-run mode)."""
        partial = {
            "changes_summary": "Applied changes",
            "files_modified": ["file.py"],
        }
        port = MockClaudePort(partial)
        prev = _make_plan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, ExecuteOutput)
        assert result.data.commit_ref == ""

    def test_missing_fields_default_to_empty(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Missing files_modified and execution_notes -> default to empty."""
        minimal = {"changes_summary": "Some changes"}
        port = MockClaudePort(minimal)
        prev = _make_plan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, ExecuteOutput)
        assert result.data.files_modified == []
        assert result.data.execution_notes == ""
        assert result.data.commit_ref == ""

    def test_completely_empty_json_defaults_all_fields(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Empty JSON object -> all fields default to empty values (dry-run)."""
        port = MockClaudePort({})
        prev = _make_plan_output()
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, ExecuteOutput)
        assert result.data.changes_summary == ""
        assert result.data.files_modified == []
        assert result.data.commit_ref == ""
        assert result.data.execution_notes == ""


# ---------------------------------------------------------------------------
# Tests: prompt construction
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    """Verify build_prompt() includes plan context and guard-rails."""

    def test_prompt_includes_plan_steps(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Prompt includes the plan steps from PlanOutput."""
        prev = _make_plan_output()
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        prompt = phase.build_prompt(ctx)

        assert "Identify the circular import" in prompt
        assert "Move the tulla.cli import" in prompt

    def test_prompt_includes_files_to_modify(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Prompt includes the files to modify from PlanOutput."""
        prev = _make_plan_output()
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        prompt = phase.build_prompt(ctx)

        assert "src/tulla/core/bad.py" in prompt
        assert "src/tulla/cli.py" in prompt

    def test_prompt_includes_change_description(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Prompt includes the change description from config."""
        prev = _make_plan_output()
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(
            tmp_path, port, prev_output=prev,
            change_description="Fix the import cycle in core module",
        )

        prompt = phase.build_prompt(ctx)

        assert "Fix the import cycle in core module" in prompt

    def test_prompt_includes_guardrails(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Prompt includes architectural guard-rails."""
        prev = _make_plan_output()
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        prompt = phase.build_prompt(ctx)

        assert "Only modify files listed in the plan" in prompt
        assert "Do not introduce new external dependencies" in prompt
        assert "Follow existing code conventions" in prompt

    def test_prompt_includes_conventional_commit_format(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Prompt includes conventional commit format with correct type mapping."""
        prev = _make_plan_output()
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(
            tmp_path, port, prev_output=prev,
            change_type="bugfix",
        )

        prompt = phase.build_prompt(ctx)

        assert "fix(scope): description" in prompt

    def test_prompt_commit_type_mapping_feature(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Feature change type maps to 'feat' in commit format."""
        prev = _make_plan_output()
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(
            tmp_path, port, prev_output=prev,
            change_type="feature",
        )

        prompt = phase.build_prompt(ctx)

        assert "feat(scope): description" in prompt

    def test_prompt_commit_type_mapping_enhancement(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Enhancement change type maps to 'feat' in commit format."""
        prev = _make_plan_output()
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(
            tmp_path, port, prev_output=prev,
            change_type="enhancement",
        )

        prompt = phase.build_prompt(ctx)

        assert "feat(scope): description" in prompt

    def test_prompt_commit_type_default_chore(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Default change_type -> 'chore' commit type in prompt."""
        prev = _make_plan_output()
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        prompt = phase.build_prompt(ctx)

        assert "chore(scope): description" in prompt

    def test_prompt_commit_type_mapping_refactor(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Refactor change type maps to 'refactor' in commit format."""
        prev = _make_plan_output()
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(
            tmp_path, port, prev_output=prev,
            change_type="refactor",
        )

        prompt = phase.build_prompt(ctx)

        assert "refactor(scope): description" in prompt

    def test_prompt_commit_type_mapping_test(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Test change type maps to 'test' in commit format."""
        prev = _make_plan_output()
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(
            tmp_path, port, prev_output=prev,
            change_type="test",
        )

        prompt = phase.build_prompt(ctx)

        assert "test(scope): description" in prompt

    def test_prompt_includes_idea_id(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Prompt includes the idea_id from PhaseContext."""
        prev = _make_plan_output()
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        prompt = phase.build_prompt(ctx)

        assert "test-idea" in prompt

    def test_prompt_includes_plan_summary(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Prompt includes the plan_summary from PlanOutput."""
        prev = _make_plan_output(
            plan_summary="Refactor the data access layer",
        )
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(tmp_path, port, prev_output=prev)

        prompt = phase.build_prompt(ctx)

        assert "Refactor the data access layer" in prompt

    def test_prompt_without_prev_output(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Prompt can be built without prev_output (graceful degradation)."""
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(tmp_path, port)

        prompt = phase.build_prompt(ctx)

        # Should still contain guard-rails even without plan data
        assert "Only modify files listed in the plan" in prompt

    def test_prompt_with_dict_prev_output(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Prompt works with prev_output as a plain dict."""
        prev_dict = {
            "plan_summary": "Refactor logging module",
            "plan_steps": ["Update logger config", "Add structured output"],
            "files_to_modify": ["src/log.py"],
            "risk_notes": "",
        }
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(tmp_path, port, prev_output=prev_dict)

        prompt = phase.build_prompt(ctx)

        assert "Refactor logging module" in prompt
        assert "Update logger config" in prompt
        assert "src/log.py" in prompt


# ---------------------------------------------------------------------------
# Tests: get_tools returns file and bash tools
# ---------------------------------------------------------------------------


class TestGetTools:
    """Verify get_tools() returns file read/write and bash tool specs."""

    def test_get_tools_returns_expected_tools(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(tmp_path, port)
        tools = phase.get_tools(ctx)

        tool_names = [t["name"] for t in tools]
        assert "Read" in tool_names
        assert "Write" in tool_names
        assert "Edit" in tool_names
        assert "Bash" in tool_names
        assert "Glob" in tool_names
        assert "Grep" in tool_names

    def test_get_tools_returns_six_tools(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        port = MockClaudePort(CANNED_EXECUTE)
        ctx = _make_ctx(tmp_path, port)
        assert len(phase.get_tools(ctx)) == 6


# ---------------------------------------------------------------------------
# Tests: parse_output error handling
# ---------------------------------------------------------------------------


class TestParseOutputErrors:
    """Verify parse_output raises ParseError for unparseable responses."""

    def test_unparseable_response_fails(
        self, phase: ExecutePhase, tmp_path: Path
    ) -> None:
        """Non-JSON response -> FAILURE status."""
        port = MockClaudePortTextOnly("This is not JSON at all")
        prev = _make_plan_output()
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

    def test_phase_id(self, phase: ExecutePhase) -> None:
        assert phase.phase_id == "execute"

    def test_timeout(self, phase: ExecutePhase) -> None:
        assert phase.timeout_s == 600.0
