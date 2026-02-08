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

    def test_upstream_facts_included_when_present(
        self, phase: D2Phase, tmp_path: Path
    ) -> None:
        """Upstream facts from config are grouped and rendered in the prompt."""
        sample_triples = [
            {
                "subject": "http://impl-ralph.io/phase#idea-42-d1",
                "predicate": "http://impl-ralph.io/phase#preserves-key_capabilities",
                "object": "[]",
            },
            {
                "subject": "http://impl-ralph.io/phase#idea-42-d1",
                "predicate": "http://impl-ralph.io/phase#preserves-ecosystem_context",
                "object": "Core MCP platform",
            },
        ]
        ctx_with_facts = PhaseContext(
            idea_id="idea-42",
            work_dir=tmp_path,
            config={"upstream_facts": sample_triples},
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.d2"),
        )
        prompt = phase.build_prompt(ctx_with_facts)
        assert "## Upstream Facts" in prompt
        assert "key_capabilities" in prompt
        assert "ecosystem_context" in prompt

    def test_upstream_facts_omitted_when_empty(
        self, phase: D2Phase, ctx: PhaseContext
    ) -> None:
        """No upstream facts section when config has no upstream_facts."""
        prompt = phase.build_prompt(ctx)
        assert "## Upstream Facts" not in prompt

    def test_upstream_facts_before_goal(
        self, phase: D2Phase, tmp_path: Path
    ) -> None:
        """Upstream facts section appears before ## Goal."""
        sample_triples = [
            {
                "subject": "http://impl-ralph.io/phase#idea-42-d1",
                "predicate": "http://impl-ralph.io/phase#preserves-key_capabilities",
                "object": "[]",
            },
        ]
        ctx_with_facts = PhaseContext(
            idea_id="idea-42",
            work_dir=tmp_path,
            config={"upstream_facts": sample_triples},
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.d2"),
        )
        prompt = phase.build_prompt(ctx_with_facts)
        facts_pos = prompt.index("## Upstream Facts")
        goal_pos = prompt.index("## Goal")
        assert facts_pos < goal_pos


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
        import json
        personas = json.loads(result.personas)
        assert len(personas) == 3
        assert result.primary_persona_jtbd == (
            "When I am building features, I want to track impact, so I can prioritise."
        )

    def test_empty_personas_when_table_empty(
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
        import json
        assert json.loads(result.personas) == []


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
        import json
        assert len(json.loads(result.data.personas)) == 3
        assert result.error is None
        assert result.duration_s > 0
