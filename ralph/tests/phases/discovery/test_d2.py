"""Tests for tulla.phases.discovery.d2 – D2Phase."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.discovery.d2 import D2Phase

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
        logger=logging.getLogger("test.d2"),
    )


@pytest.fixture()
def phase() -> D2Phase:
    """A plain D2Phase instance."""
    return D2Phase()


SAMPLE_PERSONAS = """\
# D2: Persona Discovery
**Idea**: idea-42
**Date**: 2026-02-01
**Time-box**: 20 minutes

## Persona Overview
| Persona | Role | Primary JTBD | Frequency |
|---------|------|--------------|-----------|
| Data-Driven Developer | Backend Engineer | Automate data pipelines | Daily |
| Product Manager | PM | Track feature impact | Weekly |
| DevOps Engineer | SRE | Monitor system health | Daily |

## Detailed Personas

### Persona 1: Data-Driven Developer
**Who they are**: Mid-level backend engineer.

### Persona 2: Product Manager
**Who they are**: Senior PM focused on metrics.

### Persona 3: DevOps Engineer
**Who they are**: SRE with monitoring focus.

## Cross-Persona Insights

**Common pain points**:
- Manual data collection

## JTBD Summary
When I am building features, I want to track impact, so I can prioritise.
"""


# ===================================================================
# build_prompt includes idea_id
# ===================================================================


class TestBuildPrompt:
    """D2Phase.build_prompt() tests."""

    def test_includes_idea_id(self, phase: D2Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert ctx.idea_id in prompt

    def test_includes_personas_output_path(
        self, phase: D2Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "d2-personas.md" in prompt

    def test_includes_phase_heading(
        self, phase: D2Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Phase D2: Persona Discovery" in prompt

    def test_reads_d1_inventory(
        self, phase: D2Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "d1-inventory.md" in prompt


# ===================================================================
# get_tools includes WebSearch
# ===================================================================


class TestGetTools:
    """D2Phase.get_tools() tests."""

    def test_includes_web_search(
        self, phase: D2Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        tool_names = [t["name"] for t in tools]
        assert "WebSearch" in tool_names

    def test_includes_read_write(
        self, phase: D2Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        tool_names = {t["name"] for t in tools}
        assert "Read" in tool_names
        assert "Write" in tool_names


# ===================================================================
# parse_output raises on missing file
# ===================================================================


class TestParseOutputMissing:
    """D2Phase.parse_output() when d2-personas.md is absent."""

    def test_raises_parse_error_on_missing_file(
        self, phase: D2Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError, match="d2-personas.md not found"):
            phase.parse_output(ctx, raw="anything")

    def test_parse_error_includes_context(
        self, phase: D2Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError) as exc_info:
            phase.parse_output(ctx, raw="raw-data")
        assert "work_dir" in exc_info.value.context


# ===================================================================
# parse_output succeeds with file
# ===================================================================


class TestParseOutputSuccess:
    """D2Phase.parse_output() when d2-personas.md is present."""

    def test_returns_d2_output(
        self, phase: D2Phase, ctx: PhaseContext
    ) -> None:
        personas_file = ctx.work_dir / "d2-personas.md"
        personas_file.write_text(SAMPLE_PERSONAS, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.personas_file == personas_file
        assert result.persona_count == 3

    def test_zero_personas_when_table_empty(
        self, phase: D2Phase, ctx: PhaseContext
    ) -> None:
        minimal = (
            "# D2: Persona Discovery\n"
            "## Persona Overview\n"
            "No personas found.\n"
            "## Detailed Personas\n"
        )
        personas_file = ctx.work_dir / "d2-personas.md"
        personas_file.write_text(minimal, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")
        assert result.persona_count == 0


# ===================================================================
# execute SUCCESS with mock
# ===================================================================


class _MockD2Phase(D2Phase):
    """D2Phase with a mocked run_claude that writes the personas file."""

    def __init__(self, personas_content: str) -> None:
        super().__init__()
        self._personas_content = personas_content

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "d2-personas.md"
        output_file.write_text(self._personas_content, encoding="utf-8")
        return "mock-raw-output"


class TestExecuteWithMock:
    """D2Phase.execute() end-to-end with a mocked Claude adapter."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockD2Phase(SAMPLE_PERSONAS)
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.personas_file == ctx.work_dir / "d2-personas.md"
        assert result.data.persona_count == 3
        assert result.error is None
        assert result.duration_s > 0
