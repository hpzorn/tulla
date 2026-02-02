"""Tests for tulla.phases.planning.p4 – P4Phase."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.planning.p4 import P4Phase

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

    def test_includes_plan_output_path(
        self, phase: P4Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p4-implementation-plan.md" in prompt

    def test_includes_phase_heading(
        self, phase: P4Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Phase P4: Implementation Plan" in prompt

    def test_reads_p1_p2_p3(
        self, phase: P4Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p1-discovery-context.md" in prompt
        assert "p2-codebase-analysis.md" in prompt
        assert "p3-architecture-design.md" in prompt


# ===================================================================
# get_tools includes Read, Write
# ===================================================================


class TestGetTools:
    """P4Phase.get_tools() tests."""

    def test_includes_read_write(
        self, phase: P4Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        tool_names = {t["name"] for t in tools}
        assert "Read" in tool_names
        assert "Write" in tool_names

    def test_tool_count(
        self, phase: P4Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        assert len(tools) == 2


# ===================================================================
# parse_output raises on missing file
# ===================================================================


class TestParseOutputMissing:
    """P4Phase.parse_output() when p4-implementation-plan.md is absent."""

    def test_raises_parse_error_on_missing_file(
        self, phase: P4Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError, match="p4-implementation-plan.md not found"):
            phase.parse_output(ctx, raw="anything")

    def test_parse_error_includes_context(
        self, phase: P4Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError) as exc_info:
            phase.parse_output(ctx, raw="raw-data")
        assert "work_dir" in exc_info.value.context


# ===================================================================
# parse_output succeeds with file
# ===================================================================


class TestParseOutputSuccess:
    """P4Phase.parse_output() when p4-implementation-plan.md is present."""

    def test_returns_p4_output(
        self, phase: P4Phase, ctx: PhaseContext
    ) -> None:
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(SAMPLE_IMPLEMENTATION_PLAN, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.schedule_file == plan_file
        assert result.phase_count == 3  # 3 phases
        assert result.estimated_tasks == 4  # 4 tasks (1.1, 1.2, 2.1, 3.1)

    def test_default_granularity_fields(
        self, phase: P4Phase, ctx: PhaseContext
    ) -> None:
        plan_file = ctx.work_dir / "p4-implementation-plan.md"
        plan_file.write_text(SAMPLE_IMPLEMENTATION_PLAN, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.coarse_tasks == []
        assert result.granularity_passed is True

    def test_zero_phases_when_empty(
        self, phase: P4Phase, ctx: PhaseContext
    ) -> None:
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

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
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
