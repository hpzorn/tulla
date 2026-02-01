"""Tests for ralph.phases.planning.p5 – P5Phase."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from ralph.core.phase import ParseError, PhaseContext, PhaseStatus
from ralph.phases.planning.p5 import P5Phase

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
        logger=logging.getLogger("test.p5"),
    )


@pytest.fixture()
def phase() -> P5Phase:
    """A plain P5Phase instance."""
    return P5Phase()


SAMPLE_READY = """\
# P5: Research Requests
**Idea**: idea-42
**Date**: 2026-02-01

## Status: READY TO IMPLEMENT

No blocking unknowns identified. Implementation can proceed.

## Planning Artifacts
- p1-discovery-context.md
- p2-codebase-analysis.md
- p3-architecture-design.md
- p4-implementation-plan.md

## Next Step
Execute the implementation plan in p4-implementation-plan.md

---
ready
"""

SAMPLE_BLOCKED = """\
# P5: Research Requests
**Idea**: idea-42
**Date**: 2026-02-01

## Status: BLOCKED - RESEARCH NEEDED

The following unknowns must be resolved before implementation.

## Research Requests

### RR1: MCP Rate Limits
**Blocking Task**: Task 2.1
**Question**: What are the MCP server rate limits?
**Why We Can't Proceed**: Pipeline may fail under load
**Suggested Approach**: Benchmark MCP calls
**Acceptable Answer Format**: Requests per second

### RR2: iSAQB Coverage
**Blocking Task**: Task 1.3
**Question**: Does the iSAQB schema cover all quality attributes?
**Why We Can't Proceed**: Architecture may miss quality goals
**Suggested Approach**: Query ontology-server
**Acceptable Answer Format**: List of covered attributes

## Handoff to Research-Ralph

Run: `./research-ralph.sh --idea idea-42` with focus on:
- MCP rate limits
- iSAQB coverage

After research completes, re-run planning-ralph to update the plan.

---
blocked
"""


# ===================================================================
# build_prompt includes idea_id
# ===================================================================


class TestBuildPrompt:
    """P5Phase.build_prompt() tests."""

    def test_includes_idea_id(self, phase: P5Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert ctx.idea_id in prompt

    def test_includes_research_output_path(
        self, phase: P5Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p5-research-requests.md" in prompt

    def test_includes_phase_heading(
        self, phase: P5Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Phase P5: Research Requests" in prompt

    def test_reads_p4_and_p4b(
        self, phase: P5Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p4-implementation-plan.md" in prompt
        assert "p4b-persona-walkthrough.md" in prompt


# ===================================================================
# get_tools includes Read, Write
# ===================================================================


class TestGetTools:
    """P5Phase.get_tools() tests."""

    def test_includes_read_write(
        self, phase: P5Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        tool_names = {t["name"] for t in tools}
        assert "Read" in tool_names
        assert "Write" in tool_names

    def test_tool_count(
        self, phase: P5Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        assert len(tools) == 2


# ===================================================================
# parse_output raises on missing file
# ===================================================================


class TestParseOutputMissing:
    """P5Phase.parse_output() when p5-research-requests.md is absent."""

    def test_raises_parse_error_on_missing_file(
        self, phase: P5Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError, match="p5-research-requests.md not found"):
            phase.parse_output(ctx, raw="anything")

    def test_parse_error_includes_context(
        self, phase: P5Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError) as exc_info:
            phase.parse_output(ctx, raw="raw-data")
        assert "work_dir" in exc_info.value.context


# ===================================================================
# parse_output succeeds – READY status
# ===================================================================


class TestParseOutputReady:
    """P5Phase.parse_output() with ready status."""

    def test_returns_ready_p5_output(
        self, phase: P5Phase, ctx: PhaseContext
    ) -> None:
        research_file = ctx.work_dir / "p5-research-requests.md"
        research_file.write_text(SAMPLE_READY, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.prd_file == research_file
        assert result.total_requirements == 0  # no RR headings
        assert result.phases_defined == 4  # 4 planning artifacts listed


# ===================================================================
# parse_output succeeds – BLOCKED status
# ===================================================================


class TestParseOutputBlocked:
    """P5Phase.parse_output() with blocked status."""

    def test_returns_blocked_p5_output(
        self, phase: P5Phase, ctx: PhaseContext
    ) -> None:
        research_file = ctx.work_dir / "p5-research-requests.md"
        research_file.write_text(SAMPLE_BLOCKED, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.prd_file == research_file
        assert result.total_requirements == 2  # RR1 and RR2

    def test_blocked_status_detected(
        self, phase: P5Phase, ctx: PhaseContext
    ) -> None:
        research_file = ctx.work_dir / "p5-research-requests.md"
        research_file.write_text(SAMPLE_BLOCKED, encoding="utf-8")

        # Verify the status is 'blocked' by checking the file content
        content = research_file.read_text(encoding="utf-8")
        last_lines = content.strip().splitlines()[-5:]
        assert any("blocked" in line.lower() for line in last_lines)


# ===================================================================
# execute SUCCESS with mock – ready
# ===================================================================


class _MockP5PhaseReady(P5Phase):
    """P5Phase with a mocked run_claude that writes ready output."""

    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "p5-research-requests.md"
        output_file.write_text(self._content, encoding="utf-8")
        return "mock-raw-output"


class TestExecuteWithMock:
    """P5Phase.execute() end-to-end with a mocked Claude adapter."""

    def test_execute_ready_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockP5PhaseReady(SAMPLE_READY)
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.prd_file == ctx.work_dir / "p5-research-requests.md"
        assert result.data.total_requirements == 0
        assert result.error is None
        assert result.duration_s > 0

    def test_execute_blocked_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockP5PhaseReady(SAMPLE_BLOCKED)
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.total_requirements == 2
        assert result.error is None
