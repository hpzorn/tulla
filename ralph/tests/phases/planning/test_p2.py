"""Tests for ralph.phases.planning.p2 – P2Phase."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from ralph.core.phase import ParseError, PhaseContext, PhaseStatus
from ralph.phases.planning.p2 import P2Phase

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
        logger=logging.getLogger("test.p2"),
    )


@pytest.fixture()
def phase() -> P2Phase:
    """A plain P2Phase instance."""
    return P2Phase()


SAMPLE_CODEBASE_ANALYSIS = """\
# P2: Codebase Analysis
**Idea**: idea-42
**Date**: 2026-02-01

## Skill Architecture

### Skill Structure
Skills are defined as markdown files with structured prompts.

### Key Skills for This Project

#### beamer-inovex
**Location**: ~/.claude/skills/beamer-inovex.md
**Interface**: Skill invocation
**Key Functions**: LaTeX Beamer presentations
**Limitations**: Fixed templates only

## MCP Server Architecture

### Key Servers for This Project

#### compose-scene
**Location**: ~/visual-tools/compose-scene
**Tools Exposed**: render_scene, render_container_diagram
**Input/Output Format**: JSON -> SVG/PNG

## Integration Patterns
Tools are composed via Claude's tool orchestration.

## Reusable Components

| Component | Location | Can Reuse For |
|-----------|----------|---------------|
| compose-scene | ~/visual-tools/compose-scene | Scene rendering |
| kpi-cards | ~/visual-tools/kpi-cards | KPI visualisation |
| beamer-inovex | ~/.claude/skills/ | Presentations |

## Extension Points
- Skill extension: add new .md skill files
- MCP tool addition: register new MCP server
- Template addition: add Typst/LaTeX templates

## Code Quality Observations
Follow existing MCP protocol patterns.
"""


# ===================================================================
# build_prompt includes idea_id
# ===================================================================


class TestBuildPrompt:
    """P2Phase.build_prompt() tests."""

    def test_includes_idea_id(self, phase: P2Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert ctx.idea_id in prompt

    def test_includes_analysis_output_path(
        self, phase: P2Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p2-codebase-analysis.md" in prompt

    def test_includes_phase_heading(
        self, phase: P2Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Phase P2: Codebase Analysis" in prompt

    def test_reads_p1_context(
        self, phase: P2Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p1-discovery-context.md" in prompt


# ===================================================================
# get_tools includes Read, Write, Glob, Grep
# ===================================================================


class TestGetTools:
    """P2Phase.get_tools() tests."""

    def test_includes_read_write_glob_grep(
        self, phase: P2Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        tool_names = {t["name"] for t in tools}
        assert "Read" in tool_names
        assert "Write" in tool_names
        assert "Glob" in tool_names
        assert "Grep" in tool_names


# ===================================================================
# parse_output raises on missing file
# ===================================================================


class TestParseOutputMissing:
    """P2Phase.parse_output() when p2-codebase-analysis.md is absent."""

    def test_raises_parse_error_on_missing_file(
        self, phase: P2Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError, match="p2-codebase-analysis.md not found"):
            phase.parse_output(ctx, raw="anything")

    def test_parse_error_includes_context(
        self, phase: P2Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError) as exc_info:
            phase.parse_output(ctx, raw="raw-data")
        assert "work_dir" in exc_info.value.context


# ===================================================================
# parse_output succeeds with file
# ===================================================================


class TestParseOutputSuccess:
    """P2Phase.parse_output() when p2-codebase-analysis.md is present."""

    def test_returns_p2_output(
        self, phase: P2Phase, ctx: PhaseContext
    ) -> None:
        analysis_file = ctx.work_dir / "p2-codebase-analysis.md"
        analysis_file.write_text(SAMPLE_CODEBASE_ANALYSIS, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.requirements_file == analysis_file
        assert result.requirement_count == 3  # 3 reusable components
        assert result.p0_count == 3  # 3 extension point bullets

    def test_zero_components_when_table_empty(
        self, phase: P2Phase, ctx: PhaseContext
    ) -> None:
        minimal = (
            "# P2: Codebase Analysis\n"
            "## Reusable Components\n"
            "No reusable components found.\n"
            "## Extension Points\n"
            "None identified.\n"
        )
        analysis_file = ctx.work_dir / "p2-codebase-analysis.md"
        analysis_file.write_text(minimal, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")
        assert result.requirement_count == 0


# ===================================================================
# execute SUCCESS with mock
# ===================================================================


class _MockP2Phase(P2Phase):
    """P2Phase with a mocked run_claude that writes the analysis file."""

    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "p2-codebase-analysis.md"
        output_file.write_text(self._content, encoding="utf-8")
        return "mock-raw-output"


class TestExecuteWithMock:
    """P2Phase.execute() end-to-end with a mocked Claude adapter."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockP2Phase(SAMPLE_CODEBASE_ANALYSIS)
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.requirements_file == ctx.work_dir / "p2-codebase-analysis.md"
        assert result.data.requirement_count == 3
        assert result.error is None
        assert result.duration_s > 0
