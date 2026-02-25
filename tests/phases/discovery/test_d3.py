"""Tests for tulla.phases.discovery.d3 – D3Phase."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.discovery.d3 import D3Phase

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
        logger=logging.getLogger("test.d3"),
    )


@pytest.fixture()
def phase() -> D3Phase:
    """A plain D3Phase instance."""
    return D3Phase()


SAMPLE_VALUE_MAPPING = """\
# D3: Value Mapping
**Idea**: idea-42
**Date**: 2026-02-01
**Time-box**: 20 minutes

## Value Dimensions

### User Value
| Dimension | Rating (1-5) | Evidence |
|-----------|--------------|----------|
| Pain reduction | 4 | From D2: manual data collection |
| Time savings | 3 | Reduces pipeline setup |
| Quality improvement | 4 | Better data quality |
| New capability | 5 | Automated monitoring |

**User value score**: 16/20

### Business Value
| Dimension | Rating (1-5) | Rationale |
|-----------|--------------|-----------|
| Revenue potential | 2 | Internal tool |
| Cost reduction | 4 | Less manual work |
| Competitive advantage | 3 | Better tooling |
| Strategic alignment | 5 | Core platform |

**Business value score**: 14/20

### Technical Value
| Dimension | Rating (1-5) | Rationale |
|-----------|--------------|-----------|
| Reusability | 4 | Cross-project |
| Technical debt reduction | 3 | Replaces scripts |
| Platform enhancement | 5 | Core capability |
| Learning/capability building | 3 | New patterns |

**Technical value score**: 15/20

## Effort vs. Impact Matrix

**Estimated Effort**: Medium
**Estimated Impact**: High
**Quadrant**: Major Project

## Strategic Fit

**Alignment with existing systems**:
- ontology-server: high alignment

## ROI Assessment

**ROI verdict**: Strong

## Value Summary

**Total value score**: 45/60
**Priority recommendation**: P1-High
**Confidence**: High
"""


# ===================================================================
# build_prompt includes idea_id
# ===================================================================


class TestBuildPrompt:
    """D3Phase.build_prompt() tests."""

    def test_includes_idea_id(self, phase: D3Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert ctx.idea_id in prompt

    def test_includes_value_mapping_output_path(
        self, phase: D3Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "d3-value-mapping.md" in prompt

    def test_includes_phase_heading(
        self, phase: D3Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Phase D3: Value Mapping" in prompt

    def test_reads_d1_and_d2(
        self, phase: D3Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "d1-inventory.md" in prompt
        assert "d2-personas.md" in prompt

    def test_upstream_facts_included_when_present(
        self, phase: D3Phase, tmp_path: Path
    ) -> None:
        """Upstream facts from D1 and D2 are grouped and rendered in the prompt."""
        sample_triples = [
            {
                "subject": "http://tulla.dev/phase#idea-42-d1",
                "predicate": "http://tulla.dev/phase#preserves-key_capabilities",
                "object": "[]",
            },
            {
                "subject": "http://tulla.dev/phase#idea-42-d1",
                "predicate": "http://tulla.dev/phase#preserves-ecosystem_context",
                "object": "Core MCP platform",
            },
            {
                "subject": "http://tulla.dev/phase#idea-42-d2",
                "predicate": "http://tulla.dev/phase#preserves-primary_persona_jtbd",
                "object": "When I build, I want speed",
            },
        ]
        ctx_with_facts = PhaseContext(
            idea_id="idea-42",
            work_dir=tmp_path,
            config={"upstream_facts": sample_triples},
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.d3"),
        )
        prompt = phase.build_prompt(ctx_with_facts)
        assert "## Upstream Facts" in prompt
        assert "key_capabilities" in prompt
        assert "ecosystem_context" in prompt
        assert "primary_persona_jtbd" in prompt

    def test_upstream_facts_omitted_when_empty(
        self, phase: D3Phase, ctx: PhaseContext
    ) -> None:
        """No upstream facts section when config has no upstream_facts."""
        prompt = phase.build_prompt(ctx)
        assert "## Upstream Facts" not in prompt

    def test_upstream_facts_before_goal(
        self, phase: D3Phase, tmp_path: Path
    ) -> None:
        """Upstream facts section appears before ## Goal."""
        sample_triples = [
            {
                "subject": "http://tulla.dev/phase#idea-42-d1",
                "predicate": "http://tulla.dev/phase#preserves-key_capabilities",
                "object": "[]",
            },
        ]
        ctx_with_facts = PhaseContext(
            idea_id="idea-42",
            work_dir=tmp_path,
            config={"upstream_facts": sample_triples},
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.d3"),
        )
        prompt = phase.build_prompt(ctx_with_facts)
        facts_pos = prompt.index("## Upstream Facts")
        goal_pos = prompt.index("## Goal")
        assert facts_pos < goal_pos


# ===================================================================
# get_tools
# ===================================================================


class TestGetTools:
    """D3Phase.get_tools() tests."""

    def test_includes_read_write(
        self, phase: D3Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        tool_names = {t["name"] for t in tools}
        assert "Read" in tool_names
        assert "Write" in tool_names

    def test_includes_idea_pool(
        self, phase: D3Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        tool_names = [t["name"] for t in tools]
        assert any("ontology-server" in name for name in tool_names)


# ===================================================================
# parse_output raises on missing file
# ===================================================================


class TestParseOutputMissing:
    """D3Phase.parse_output() when d3-value-mapping.md is absent."""

    def test_raises_parse_error_on_missing_file(
        self, phase: D3Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError, match="d3-value-mapping.md not found"):
            phase.parse_output(ctx, raw="anything")

    def test_parse_error_includes_context(
        self, phase: D3Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError) as exc_info:
            phase.parse_output(ctx, raw="raw-data")
        assert "work_dir" in exc_info.value.context


# ===================================================================
# parse_output succeeds with file
# ===================================================================


class TestParseOutputSuccess:
    """D3Phase.parse_output() when d3-value-mapping.md is present."""

    def test_returns_d3_output(
        self, phase: D3Phase, ctx: PhaseContext
    ) -> None:
        value_file = ctx.work_dir / "d3-value-mapping.md"
        value_file.write_text(SAMPLE_VALUE_MAPPING, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.value_mapping_file == value_file
        assert result.quadrant == "Major Project"
        assert result.verdict == "P1-High | Strong ROI | High confidence"

    def test_empty_verdict_when_missing(
        self, phase: D3Phase, ctx: PhaseContext
    ) -> None:
        minimal = (
            "# D3: Value Mapping\n"
            "## Value Summary\n"
            "No data.\n"
        )
        value_file = ctx.work_dir / "d3-value-mapping.md"
        value_file.write_text(minimal, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")
        assert result.verdict == ""
        assert result.quadrant == "Unknown"


# ===================================================================
# execute SUCCESS with mock
# ===================================================================


class _MockD3Phase(D3Phase):
    """D3Phase with a mocked run_claude that writes the value mapping file."""

    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "d3-value-mapping.md"
        output_file.write_text(self._content, encoding="utf-8")
        return "mock-raw-output"


class TestExecuteWithMock:
    """D3Phase.execute() end-to-end with a mocked Claude adapter."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockD3Phase(SAMPLE_VALUE_MAPPING)
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.value_mapping_file == ctx.work_dir / "d3-value-mapping.md"
        assert result.data.quadrant == "Major Project"
        assert result.data.verdict == "P1-High | Strong ROI | High confidence"
        assert result.error is None
        assert result.duration_s > 0
