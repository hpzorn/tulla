"""Tests for tulla.phases.planning.p1 – P1Phase."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.planning.p1 import P1Phase

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx(tmp_path: Path) -> PhaseContext:
    """Standard PhaseContext pointing at a temporary work directory."""
    return PhaseContext(
        idea_id="idea-42",
        work_dir=tmp_path,
        config={"discovery_dir": "/tmp/discovery-idea-42"},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.p1"),
    )


@pytest.fixture()
def phase() -> P1Phase:
    """A plain P1Phase instance."""
    return P1Phase()


SAMPLE_CONTEXT = """\
# P1: Discovery Context
**Idea**: idea-42
**Date**: 2026-02-01
**Discovery Source**: /tmp/discovery-idea-42

## Idea Summary
A sample idea for testing the planning pipeline.

## User Persona
Data-driven developer who needs faster feedback loops.

## Value Proposition
Reduce iteration time by 50% through automated planning.

## Existing Capabilities (from D1)

### Available Tools
| Tool/Skill | Type | Relevance |
|------------|------|-----------|
| mcp__ontology-server__get_idea | MCP | High |
| mcp__ontology-server__query | MCP | Medium |
| beamer-inovex | Skill | High |

### Validated Technologies
Python 3.11+, Typst, MCP protocol

## Gaps to Address (from D4)

| Gap | Priority | Type |
|-----|----------|------|
| No API endpoint | P0 | Implementation |
| Missing auth layer | P0 | Implementation |

## Open Research Questions (from D5)
None — all resolved by downstream research.

## Planning Constraints
- Must use: existing MCP tools
- Should avoid: monolithic architecture
- Success criteria: all phases pass
"""


# ===================================================================
# build_prompt includes idea_id
# ===================================================================


class TestBuildPrompt:
    """P1Phase.build_prompt() tests."""

    def test_includes_idea_id(self, phase: P1Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert ctx.idea_id in prompt

    def test_includes_context_output_path(self, phase: P1Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p1-discovery-context.md" in prompt

    def test_includes_phase_heading(self, phase: P1Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Phase P1: Load Discovery Context" in prompt

    def test_includes_discovery_dir(self, phase: P1Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "/tmp/discovery-idea-42" in prompt

    def test_includes_research_instructions_when_provided(
        self, phase: P1Phase, tmp_path: Path
    ) -> None:
        ctx = PhaseContext(
            idea_id="idea-42",
            work_dir=tmp_path,
            config={
                "discovery_dir": "/tmp/discovery",
                "research_dir": "/tmp/research-idea-42",
            },
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.p1"),
        )
        prompt = phase.build_prompt(ctx)
        assert "/tmp/research-idea-42" in prompt
        assert "research findings" in prompt.lower()

    def test_no_research_block_when_absent(self, phase: P1Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "SUPERSEDE" not in prompt


# ===================================================================
# get_tools includes idea_pool
# ===================================================================


class TestGetTools:
    """P1Phase.get_tools() tests."""

    def test_includes_idea_pool(self, phase: P1Phase, ctx: PhaseContext) -> None:
        tools = phase.get_tools(ctx)
        tool_names = [t["name"] for t in tools]
        assert any("ontology-server" in name for name in tool_names)

    def test_includes_read_write_glob(self, phase: P1Phase, ctx: PhaseContext) -> None:
        tools = phase.get_tools(ctx)
        tool_names = {t["name"] for t in tools}
        assert "Read" in tool_names
        assert "Write" in tool_names
        assert "Glob" in tool_names


# ===================================================================
# parse_output raises on missing file
# ===================================================================


class TestParseOutputMissing:
    """P1Phase.parse_output() when p1-discovery-context.md is absent."""

    def test_raises_parse_error_on_missing_file(self, phase: P1Phase, ctx: PhaseContext) -> None:
        with pytest.raises(ParseError, match="p1-discovery-context.md not found"):
            phase.parse_output(ctx, raw="anything")

    def test_parse_error_includes_context(self, phase: P1Phase, ctx: PhaseContext) -> None:
        with pytest.raises(ParseError) as exc_info:
            phase.parse_output(ctx, raw="raw-data")
        assert "work_dir" in exc_info.value.context


# ===================================================================
# parse_output succeeds with file
# ===================================================================


class TestParseOutputSuccess:
    """P1Phase.parse_output() when p1-discovery-context.md is present."""

    def test_returns_p1_output(self, phase: P1Phase, ctx: PhaseContext) -> None:
        context_file = ctx.work_dir / "p1-discovery-context.md"
        context_file.write_text(SAMPLE_CONTEXT, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.context_file == context_file
        assert result.triples_loaded == 3  # 3 tools in Available Tools table
        assert len(result.ontologies_queried) >= 1

    def test_zero_triples_when_table_empty(self, phase: P1Phase, ctx: PhaseContext) -> None:
        minimal = (
            "# P1: Discovery Context\n**Discovery Source**: /tmp/disc\n## Idea Summary\nTest.\n"
        )
        context_file = ctx.work_dir / "p1-discovery-context.md"
        context_file.write_text(minimal, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")
        assert result.triples_loaded == 0


# ===================================================================
# execute SUCCESS with mock
# ===================================================================


class _MockP1Phase(P1Phase):
    """P1Phase with a mocked run_claude that writes the context file."""

    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content

    def run_claude(self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]) -> Any:
        output_file = ctx.work_dir / "p1-discovery-context.md"
        output_file.write_text(self._content, encoding="utf-8")
        return "mock-raw-output"


class TestExecuteWithMock:
    """P1Phase.execute() end-to-end with a mocked Claude adapter."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockP1Phase(SAMPLE_CONTEXT)
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.context_file == ctx.work_dir / "p1-discovery-context.md"
        assert result.data.triples_loaded == 3
        assert result.error is None
        assert result.duration_s > 0
