"""Tests for tulla.phases.planning.p4 – P4Phase."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.planning.p4 import (
    P4Phase,
    _check_homogeneity,
    _extract_task_details,
    _extract_task_files,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx(tmp_path: Path) -> PhaseContext:
    """Standard PhaseContext pointing at a temporary work directory."""
    return PhaseContext(
        idea_id="idea-42",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.p4"),
    )


@pytest.fixture()
def phase() -> P4Phase:
    """A plain P4Phase instance."""
    return P4Phase()


SAMPLE_IMPLEMENTATION_PLAN = """\
# P4: Implementation Plan
**Idea**: idea-42
**Date**: 2026-02-01
**Estimated Effort**: M

## Prerequisites

Before starting:
- [ ] Python 3.11+ installed
- [ ] MCP servers running

## Implementation Phases

### Phase 1: Core Pipeline (P0 - Critical Path)

**Goal**: Set up phase execution framework
**Deliverable**: Working pipeline with P1-P5 phases

#### Task 1.1: Create P1 Phase
**File(s)**: `tulla/src/tulla/phases/planning/p1.py`
**Action**: Create
**Details**: Implement P1Phase class
**Dependencies**: None
**Verification**: Unit tests pass

#### Task 1.2: Create P2 Phase
**File(s)**: `tulla/src/tulla/phases/planning/p2.py`
**Action**: Create
**Details**: Implement P2Phase class
**Dependencies**: Task 1.1
**Verification**: Unit tests pass

### Phase 2: Integration (P1 - Important)

**Goal**: Connect phases together
**Deliverable**: End-to-end pipeline

#### Task 2.1: Create Pipeline Factory
**File(s)**: `tulla/src/tulla/phases/planning/pipeline.py`
**Action**: Create
**Details**: Implement planning_pipeline() factory
**Dependencies**: Task 1.2
**Verification**: Integration test passes

### Phase 3: Polish (P2 - Nice to Have)

**Goal**: Add CLI and documentation
**Deliverable**: User-facing CLI

#### Task 3.1: Create CLI Entry Point
**File(s)**: `tulla/src/tulla/phases/planning/__main__.py`
**Action**: Create
**Details**: Click CLI with options
**Dependencies**: Task 2.1
**Verification**: CLI help works

## File Changes Summary

| File | Action | Phase | Lines (est) |
|------|--------|-------|-------------|
| `p1.py` | Create | 1 | ~150 |
| `p2.py` | Create | 1 | ~150 |
| `pipeline.py` | Create | 2 | ~50 |
| `__main__.py` | Create | 3 | ~40 |

## Testing Plan

### Unit Tests
| Test | What It Verifies |
|------|------------------|
| test_p1 | P1Phase build/parse/execute |
| test_p2 | P2Phase build/parse/execute |

### Integration Tests
| Test | What It Verifies |
|------|------------------|
| test_pipeline | End-to-end pipeline |

### Manual Verification
1. Run pipeline: Expected success

## Rollback Plan
Revert git commits.

## Success Criteria
- [ ] All phases implemented
- [ ] Tests pass
- [ ] Pipeline runs end-to-end

## Blocked Tasks (Need Research)

| Task | Blocked By | Research Question |
|------|------------|-------------------|
"""


# ===================================================================
# build_prompt includes idea_id
# ===================================================================


class TestBuildPrompt:
    """P4Phase.build_prompt() tests."""

    def test_includes_idea_id(self, phase: P4Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert ctx.idea_id in prompt

    def test_includes_plan_output_path(self, phase: P4Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p4-implementation-plan.md" in prompt

    def test_includes_phase_heading(self, phase: P4Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Phase P4: Implementation Plan" in prompt

    def test_reads_p1_p2_p3(self, phase: P4Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p1-discovery-context.md" in prompt
        assert "p2-codebase-analysis.md" in prompt
        assert "p3-architecture-design.md" in prompt


# ===================================================================
# get_tools includes Read, Write
# ===================================================================


class TestGetTools:
    """P4Phase.get_tools() tests."""

    def test_includes_read_write(self, phase: P4Phase, ctx: PhaseContext) -> None:
        tools = phase.get_tools(ctx)
        tool_names = {t["name"] for t in tools}
        assert "Read" in tool_names
        assert "Write" in tool_names

    def test_tool_count(self, phase: P4Phase, ctx: PhaseContext) -> None:
        tools = phase.get_tools(ctx)
        assert len(tools) == 2


# ===================================================================
# parse_output raises on missing file
# ===================================================================


class TestParseOutputMissing:
    """P4Phase.parse_output() when p4-implementation-plan.md is absent."""

    def test_raises_parse_error_on_missing_file(self, phase: P4Phase, ctx: PhaseContext) -> None:
        with pytest.raises(ParseError, match="p4-implementation-plan.md not found"):
            phase.parse_output(ctx, raw="anything")

    def test_parse_error_includes_context(self, phase: P4Phase, ctx: PhaseContext) -> None:
        with pytest.raises(ParseError) as exc_info:
            phase.parse_output(ctx, raw="raw-data")
        assert "work_dir" in exc_info.value.context


# ===================================================================
# parse_output succeeds with file
# ===================================================================


class TestParseOutputSuccess:
    """P4Phase.parse_output() when p4-implementation-plan.md is present."""

    def test_returns_p4_output(self, phase: P4Phase, ctx: PhaseContext) -> None:
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(SAMPLE_IMPLEMENTATION_PLAN, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.schedule_file == plan_file
        assert result.phase_count == 3  # 3 phases
        assert result.estimated_tasks == 4  # 4 tasks (1.1, 1.2, 2.1, 3.1)

    def test_default_granularity_fields(self, phase: P4Phase, ctx: PhaseContext) -> None:
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(SAMPLE_IMPLEMENTATION_PLAN, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.coarse_tasks == []
        assert result.granularity_passed is True

    def test_zero_phases_when_empty(self, phase: P4Phase, ctx: PhaseContext) -> None:
        minimal = (
            "# P4: Implementation Plan\n"
            "## Implementation Phases\n"
            "No phases defined yet.\n"
            "## File Changes Summary\n"
        )
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(minimal, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")
        assert result.phase_count == 0
        assert result.estimated_tasks == 0


# ===================================================================
# execute SUCCESS with mock
# ===================================================================


class _MockP4Phase(P4Phase):
    """P4Phase with a mocked run_claude that writes the plan file."""

    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content

    def run_claude(self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]) -> Any:
        output_file = ctx.work_dir / "p4-implementation-plan.md"
        output_file.write_text(self._content, encoding="utf-8")
        return "mock-raw-output"


class TestExecuteWithMock:
    """P4Phase.execute() end-to-end with a mocked Claude adapter."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockP4Phase(SAMPLE_IMPLEMENTATION_PLAN)
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.schedule_file == ctx.work_dir / "p4-implementation-plan.md"
        assert result.data.phase_count == 3
        assert result.data.estimated_tasks == 4
        assert result.error is None
        assert result.duration_s > 0


# ===================================================================
# _check_homogeneity
# ===================================================================


class TestCheckHomogeneity:
    """Tests for _check_homogeneity() helper."""

    def test_same_basename_returns_true(self) -> None:
        assert _check_homogeneity(["a/__init__.py", "b/__init__.py"]) is True

    def test_different_name_and_extension_returns_false(self) -> None:
        assert _check_homogeneity(["a/foo.py", "b/bar.ts"]) is False

    def test_same_extension_returns_true(self) -> None:
        assert _check_homogeneity(["a/foo.py", "b/bar.py"]) is True

    def test_empty_list_returns_true(self) -> None:
        assert _check_homogeneity([]) is True

    def test_single_file_returns_true(self) -> None:
        assert _check_homogeneity(["a/foo.py"]) is True

    def test_no_extension_different_names_returns_false(self) -> None:
        assert _check_homogeneity(["a/Makefile", "b/Dockerfile"]) is False

    def test_mixed_extensions_returns_false(self) -> None:
        assert _check_homogeneity(["a/foo.py", "b/bar.py", "c/baz.ts"]) is False


# ===================================================================
# _extract_task_files / _extract_task_details
# ===================================================================


class TestExtractTaskFiles:
    """Tests for _extract_task_files() helper."""

    def test_single_backtick_file(self) -> None:
        body = "Create file\n**File(s)**: `src/foo.py`\n**Action**: Create"
        assert _extract_task_files(body) == ["src/foo.py"]

    def test_multiple_comma_separated(self) -> None:
        body = "**File(s)**: `a.py`, `b.py`, `c.ts`\n**Action**: Modify"
        assert _extract_task_files(body) == ["a.py", "b.py", "c.ts"]

    def test_no_files_line(self) -> None:
        body = "No files here\n**Action**: Create"
        assert _extract_task_files(body) == []


class TestExtractTaskDetails:
    """Tests for _extract_task_details() helper."""

    def test_extracts_details_text(self) -> None:
        body = "stuff\n**Details**: Implement P1Phase class\n**Dependencies**: None"
        assert _extract_task_details(body) == "Implement P1Phase class"

    def test_no_details_returns_empty(self) -> None:
        body = "No details field here"
        assert _extract_task_details(body) == ""


# ===================================================================
# Per-task granularity extraction
# ===================================================================

COARSE_TASK_PLAN = """\
# P4: Implementation Plan
**Idea**: idea-42
**Date**: 2026-02-01
**Estimated Effort**: L

## Implementation Phases

### Phase 1: Bootstrap (P0 - Critical Path)

**Goal**: Set up everything
**Deliverable**: All files

#### Task 1.1: Bootstrap All Modules
**File(s)**: `src/a.py`, `src/b.ts`, `src/c.go`, `src/d.rs`, `src/e.rb`, `src/f.java`, `src/g.cpp`
**Action**: Create
**Details**: Create files
**Dependencies**: None
**Verification**: Tests pass

### Phase 2: Integration (P1 - Important)

**Goal**: Wire up
**Deliverable**: Integration

#### Task 2.1: Single File Task
**File(s)**: `src/main.py`
**Action**: Modify
**Details**: Update the main entry point with the new configuration loader and validation logic
**Dependencies**: Task 1.1
**Verification**: Unit tests pass

## File Changes Summary

| File | Action | Phase | Lines (est) |
|------|--------|-------|-------------|
| `a.py` | Create | 1 | ~10 |
"""

# Aliases required by prd:req-64-2-4
SAMPLE_PLAN_WITH_COARSE_TASK = COARSE_TASK_PLAN

SAMPLE_PLAN_WITH_HOMOGENEOUS = """\
# P4: Implementation Plan
**Idea**: idea-42
**Date**: 2026-02-01
**Estimated Effort**: M

## Implementation Phases

### Phase 1: Init Modules (P0 - Critical Path)

**Goal**: Create init files for every package
**Deliverable**: Package initialisation

#### Task 1.1: Create Package Inits
**File(s)**: `src/a/__init__.py`, `src/b/__init__.py`, `src/c/__init__.py`, `src/d/__init__.py`
**Action**: Create
**Details**: Create init
**Dependencies**: None
**Verification**: Import succeeds

### Phase 2: Tests (P1 - Important)

**Goal**: Add test stubs
**Deliverable**: Test files

#### Task 2.1: Create Test Stubs
**File(s)**: `tests/test_a.py`, `tests/test_b.py`, `tests/test_c.py`
**Action**: Create
**Details**: Stub
**Dependencies**: Task 1.1
**Verification**: pytest collects

## File Changes Summary

| File | Action | Phase | Lines (est) |
|------|--------|-------|-------------|
| `__init__.py` | Create | 1 | ~5 |
"""


class TestPerTaskGranularity:
    """Tests for per-task granularity extraction in parse_output()."""

    def test_sample_plan_all_fine_grained(self, phase: P4Phase, ctx: PhaseContext) -> None:
        """SAMPLE_IMPLEMENTATION_PLAN has all 1-file tasks -> no coarse tasks."""
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(SAMPLE_IMPLEMENTATION_PLAN, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.coarse_tasks == []
        assert result.granularity_passed is True

    def test_coarse_task_detected(self, phase: P4Phase, ctx: PhaseContext) -> None:
        """Plan with 7-file non-homogeneous short-detail task -> 1 coarse task."""
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(COARSE_TASK_PLAN, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert len(result.coarse_tasks) == 1
        assert result.coarse_tasks[0]["task"] == "1.1"
        assert result.coarse_tasks[0]["file_count"] == 7
        assert result.coarse_tasks[0]["homogeneous"] is False
        assert result.granularity_passed is False

    def test_coarse_task_metrics(self, phase: P4Phase, ctx: PhaseContext) -> None:
        """Verify word_count and wpf on the detected coarse task."""
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(COARSE_TASK_PLAN, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        entry = result.coarse_tasks[0]
        # "Create files" -> 2 words, 7 files -> wpf = 2/7 ≈ 0.29
        assert entry["word_count"] == 2
        assert entry["wpf"] < 1.0

    def test_fine_grained_task_not_flagged(self, phase: P4Phase, ctx: PhaseContext) -> None:
        """Task 2.1 (single file, detailed description) should NOT be flagged."""
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(COARSE_TASK_PLAN, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        flagged_ids = [t["task"] for t in result.coarse_tasks]
        assert "2.1" not in flagged_ids

    def test_custom_thresholds_from_config(self, phase: P4Phase, tmp_path: Path) -> None:
        """Config thresholds override defaults."""
        ctx = PhaseContext(
            idea_id="idea-42",
            work_dir=tmp_path,
            config={"max_files_per_requirement": 10, "min_wpf_blocking": 1.0},
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.p4"),
        )
        plan_file = tmp_path / "p4-implementation-plan.md"
        plan_file.write_text(COARSE_TASK_PLAN, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        # With max_files=10, the 7-file task no longer exceeds threshold
        assert result.coarse_tasks == []
        assert result.granularity_passed is True


# ===================================================================
# TestGranularityMetrics (prd:req-64-2-4)
# ===================================================================


class TestGranularityMetrics:
    """Granularity metrics: fine plan passes, coarse detected, homogeneous exempt."""

    def test_fine_plan_passes(self, phase: P4Phase, ctx: PhaseContext) -> None:
        """A plan with only fine-grained tasks has no coarse flags."""
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(SAMPLE_IMPLEMENTATION_PLAN, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.coarse_tasks == []
        assert result.granularity_passed is True

    def test_coarse_detected(self, phase: P4Phase, ctx: PhaseContext) -> None:
        """SAMPLE_PLAN_WITH_COARSE_TASK triggers coarse detection."""
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(SAMPLE_PLAN_WITH_COARSE_TASK, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert len(result.coarse_tasks) >= 1
        assert result.granularity_passed is False

    def test_homogeneous_exempt(self, phase: P4Phase, ctx: PhaseContext) -> None:
        """SAMPLE_PLAN_WITH_HOMOGENEOUS multi-file tasks are exempt from coarse detection."""
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(SAMPLE_PLAN_WITH_HOMOGENEOUS, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        # Both tasks have homogeneous files (same basename or same extension),
        # so they should be exempt even though file_count > 3.
        assert result.coarse_tasks == []
        assert result.granularity_passed is True


# ===================================================================
# TestHomogeneityCheck (prd:req-64-2-4)
# ===================================================================


class TestHomogeneityCheck:
    """Tests for _check_homogeneity(): single, same base/ext, hetero."""

    def test_single_file(self) -> None:
        """A single file is always homogeneous."""
        assert _check_homogeneity(["src/foo.py"]) is True

    def test_same_basename(self) -> None:
        """Files sharing the same basename are homogeneous."""
        assert _check_homogeneity(["a/__init__.py", "b/__init__.py", "c/__init__.py"]) is True

    def test_same_extension(self) -> None:
        """Files sharing the same extension are homogeneous."""
        assert _check_homogeneity(["a/foo.py", "b/bar.py", "c/baz.py"]) is True

    def test_heterogeneous(self) -> None:
        """Files with different basenames and extensions are heterogeneous."""
        assert _check_homogeneity(["a/foo.py", "b/bar.ts", "c/baz.go"]) is False


# ===================================================================
# validate_output advisory gate (ADR-64-2)
# ===================================================================


class TestValidateOutputAdvisory:
    """P4Phase.validate_output() logs warnings but never raises."""

    def test_no_warnings_when_no_coarse_tasks(
        self, phase: P4Phase, ctx: PhaseContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        """validate_output() is silent when granularity_passed is True."""
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(SAMPLE_IMPLEMENTATION_PLAN, encoding="utf-8")
        parsed = phase.parse_output(ctx, raw="raw")

        with caplog.at_level(logging.WARNING, logger="test.p4"):
            phase.validate_output(ctx, parsed)

        assert not any("P4 advisory" in r.message for r in caplog.records)

    def test_logs_warning_per_coarse_task(
        self, phase: P4Phase, ctx: PhaseContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Each coarse task produces a ctx.logger.warning."""
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(COARSE_TASK_PLAN, encoding="utf-8")
        parsed = phase.parse_output(ctx, raw="raw")

        with caplog.at_level(logging.WARNING, logger="test.p4"):
            phase.validate_output(ctx, parsed)

        advisory_records = [r for r in caplog.records if "P4 advisory" in r.message]
        assert len(advisory_records) == len(parsed.coarse_tasks)
        assert "Task 1.1" in advisory_records[0].message

    def test_echoes_to_stderr_per_coarse_task(
        self, phase: P4Phase, ctx: PhaseContext, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Each coarse task produces a click.echo to stderr."""
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(COARSE_TASK_PLAN, encoding="utf-8")
        parsed = phase.parse_output(ctx, raw="raw")

        phase.validate_output(ctx, parsed)

        captured = capsys.readouterr()
        assert "P4 advisory" in captured.err
        assert "Task 1.1" in captured.err

    def test_never_raises(self, phase: P4Phase, ctx: PhaseContext) -> None:
        """validate_output() must never raise ValueError (advisory only)."""
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(COARSE_TASK_PLAN, encoding="utf-8")
        parsed = phase.parse_output(ctx, raw="raw")

        # Must not raise -- advisory only per ADR-64-2
        phase.validate_output(ctx, parsed)

    def test_execute_succeeds_with_coarse(
        self, ctx: PhaseContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        """execute() returns SUCCESS even when coarse tasks are detected."""
        phase = _MockP4PhaseCoarse(SAMPLE_PLAN_WITH_COARSE_TASK)

        with caplog.at_level(logging.WARNING, logger="test.p4"):
            result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.granularity_passed is False
        assert len(result.data.coarse_tasks) >= 1
        assert result.error is None


class _MockP4PhaseCoarse(P4Phase):
    """P4Phase mock that writes a coarse-task plan."""

    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content

    def run_claude(self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]) -> Any:
        output_file = ctx.work_dir / "p4-implementation-plan.md"
        output_file.write_text(self._content, encoding="utf-8")
        return "mock-raw-output"


class TestExecuteWithCoarseTasksReturnsSuccess:
    """execute() returns SUCCESS even when coarse tasks are detected."""

    def test_execute_success_despite_coarse_tasks(
        self, ctx: PhaseContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verification: Mock P4Phase with coarse-task plan -> SUCCESS."""
        phase = _MockP4PhaseCoarse(COARSE_TASK_PLAN)

        with caplog.at_level(logging.WARNING, logger="test.p4"):
            result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.granularity_passed is False
        assert len(result.data.coarse_tasks) == 1
        assert result.error is None

        # Advisory warnings were logged
        advisory_records = [r for r in caplog.records if "P4 advisory" in r.message]
        assert len(advisory_records) >= 1
