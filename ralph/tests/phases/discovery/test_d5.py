"""Tests for tulla.phases.discovery.d5 – D5Phase."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.discovery.d5 import D5Phase

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx_upstream(tmp_path: Path) -> PhaseContext:
    """PhaseContext configured for upstream mode."""
    return PhaseContext(
        idea_id="idea-42",
        work_dir=tmp_path,
        config={"mode": "upstream"},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.d5"),
    )


@pytest.fixture()
def ctx_downstream(tmp_path: Path) -> PhaseContext:
    """PhaseContext configured for downstream mode."""
    return PhaseContext(
        idea_id="idea-42",
        work_dir=tmp_path,
        config={"mode": "downstream"},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.d5"),
    )


@pytest.fixture()
def ctx_default(tmp_path: Path) -> PhaseContext:
    """PhaseContext with no mode set (defaults to upstream)."""
    return PhaseContext(
        idea_id="idea-42",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.d5"),
    )


@pytest.fixture()
def phase() -> D5Phase:
    """A plain D5Phase instance."""
    return D5Phase()


SAMPLE_RESEARCH_BRIEF = """\
# D5: Research Brief
**Idea**: idea-42
**Date**: 2026-02-01
**Mode**: Upstream (Discovery -> Research)

## Discovery Summary

### What We Learned
- **Users**: Data-Driven Developer needing automation
- **Value**: High strategic alignment (45/60)
- **Gaps**: Missing API endpoint, auth layer

### Priority Score
From D3 value mapping: 45/60 - P1-High

## Research Questions (Prioritized by Value)

### High Priority (Must answer before implementation)
1. **RQ**: How should the API authenticate?
   **Business rationale**: Security is a blocker
   **Success criteria**: Auth pattern selected

## Constraints for Research
- **User constraints**: Must be simple CLI-first
- **Technical constraints**: Python 3.11+
- **Business constraints**: Internal tool budget

## Success Definition
Research is successful if it answers auth and scaling questions.

research
"""

SAMPLE_PRODUCT_SPEC = """\
# D5: Product Specification
**Idea**: idea-42
**Date**: 2026-02-01
**Mode**: Downstream (Research -> Product)

## Executive Summary
An automated data pipeline tool for backend engineers.

## User Story
As a Data-Driven Developer,
I want to automate data pipelines,
So that I can focus on analysis.

## Research Foundation
Research validated the need for CLI-first approach.

## Product Requirements

### Must Have (P0)
- [ ] CLI interface for pipeline management
- [ ] API endpoint for automation

### Should Have (P1)
- [ ] Dashboard for monitoring

### Nice to Have (P2)
- [ ] Slack notifications

## Success Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Pipeline setup time | <5 min | Timed test |

## Integration Points
| System | Integration | Complexity |
|--------|-------------|------------|
| ontology-server | SPARQL queries | Medium |

implement
"""


# ===================================================================
# build_prompt – upstream mode
# ===================================================================


class TestBuildPromptUpstream:
    """D5Phase.build_prompt() in upstream mode."""

    def test_includes_idea_id(
        self, phase: D5Phase, ctx_upstream: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx_upstream)
        assert ctx_upstream.idea_id in prompt

    def test_includes_research_brief_output(
        self, phase: D5Phase, ctx_upstream: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx_upstream)
        assert "d5-research-brief.md" in prompt

    def test_includes_upstream_heading(
        self, phase: D5Phase, ctx_upstream: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx_upstream)
        assert "UPSTREAM" in prompt

    def test_reads_all_previous_phases(
        self, phase: D5Phase, ctx_upstream: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx_upstream)
        assert "d1-inventory.md" in prompt
        assert "d2-personas.md" in prompt
        assert "d3-value-mapping.md" in prompt
        assert "d4-gap-analysis.md" in prompt


# ===================================================================
# build_prompt – downstream mode
# ===================================================================


class TestBuildPromptDownstream:
    """D5Phase.build_prompt() in downstream mode."""

    def test_includes_product_spec_output(
        self, phase: D5Phase, ctx_downstream: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx_downstream)
        assert "d5-product-spec.md" in prompt

    def test_includes_downstream_heading(
        self, phase: D5Phase, ctx_downstream: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx_downstream)
        assert "DOWNSTREAM" in prompt


# ===================================================================
# build_prompt – default mode
# ===================================================================


class TestBuildPromptDefault:
    """D5Phase.build_prompt() defaults to upstream."""

    def test_defaults_to_upstream(
        self, phase: D5Phase, ctx_default: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx_default)
        assert "d5-research-brief.md" in prompt
        assert "UPSTREAM" in prompt


# ===================================================================
# get_tools – mode-dependent
# ===================================================================


class TestGetTools:
    """D5Phase.get_tools() tests."""

    def test_upstream_includes_capture_seed(
        self, phase: D5Phase, ctx_upstream: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx_upstream)
        tool_names = [t["name"] for t in tools]
        assert "mcp__ontology-server__capture_seed" in tool_names

    def test_downstream_includes_glob(
        self, phase: D5Phase, ctx_downstream: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx_downstream)
        tool_names = [t["name"] for t in tools]
        assert "Glob" in tool_names

    def test_both_include_read_write(
        self, phase: D5Phase, ctx_upstream: PhaseContext, ctx_downstream: PhaseContext
    ) -> None:
        for ctx in [ctx_upstream, ctx_downstream]:
            tools = phase.get_tools(ctx)
            tool_names = {t["name"] for t in tools}
            assert "Read" in tool_names
            assert "Write" in tool_names

    def test_both_include_append_to_idea(
        self, phase: D5Phase, ctx_upstream: PhaseContext, ctx_downstream: PhaseContext
    ) -> None:
        for ctx in [ctx_upstream, ctx_downstream]:
            tools = phase.get_tools(ctx)
            tool_names = [t["name"] for t in tools]
            assert "mcp__ontology-server__append_to_idea" in tool_names


# ===================================================================
# parse_output raises on missing file
# ===================================================================


class TestParseOutputMissing:
    """D5Phase.parse_output() when output file is absent."""

    def test_raises_parse_error_upstream(
        self, phase: D5Phase, ctx_upstream: PhaseContext
    ) -> None:
        with pytest.raises(ParseError, match="d5-research-brief.md not found"):
            phase.parse_output(ctx_upstream, raw="anything")

    def test_raises_parse_error_downstream(
        self, phase: D5Phase, ctx_downstream: PhaseContext
    ) -> None:
        with pytest.raises(ParseError, match="d5-product-spec.md not found"):
            phase.parse_output(ctx_downstream, raw="anything")

    def test_parse_error_includes_mode(
        self, phase: D5Phase, ctx_upstream: PhaseContext
    ) -> None:
        with pytest.raises(ParseError) as exc_info:
            phase.parse_output(ctx_upstream, raw="raw-data")
        assert "mode" in exc_info.value.context
        assert exc_info.value.context["mode"] == "upstream"


# ===================================================================
# parse_output succeeds – upstream
# ===================================================================


class TestParseOutputUpstream:
    """D5Phase.parse_output() for upstream mode."""

    def test_returns_d5_output_upstream(
        self, phase: D5Phase, ctx_upstream: PhaseContext
    ) -> None:
        brief_file = ctx_upstream.work_dir / "d5-research-brief.md"
        brief_file.write_text(SAMPLE_RESEARCH_BRIEF, encoding="utf-8")

        result = phase.parse_output(ctx_upstream, raw="raw")

        assert result.output_file == brief_file
        assert result.mode == "upstream"
        assert result.recommendation == "research"


# ===================================================================
# parse_output succeeds – downstream
# ===================================================================


class TestParseOutputDownstream:
    """D5Phase.parse_output() for downstream mode."""

    def test_returns_d5_output_downstream(
        self, phase: D5Phase, ctx_downstream: PhaseContext
    ) -> None:
        spec_file = ctx_downstream.work_dir / "d5-product-spec.md"
        spec_file.write_text(SAMPLE_PRODUCT_SPEC, encoding="utf-8")

        result = phase.parse_output(ctx_downstream, raw="raw")

        assert result.output_file == spec_file
        assert result.mode == "downstream"
        assert result.recommendation == "implement"


# ===================================================================
# recommendation extraction
# ===================================================================


class TestRecommendationExtraction:
    """Test recommendation keyword extraction from output."""

    def test_defaults_to_research_for_upstream(
        self, phase: D5Phase, ctx_upstream: PhaseContext
    ) -> None:
        brief_file = ctx_upstream.work_dir / "d5-research-brief.md"
        brief_file.write_text(
            "# D5: Research Brief\nNo recommendation keyword here.\n",
            encoding="utf-8",
        )
        result = phase.parse_output(ctx_upstream, raw="raw")
        assert result.recommendation == "research"

    def test_defaults_to_implement_for_downstream(
        self, phase: D5Phase, ctx_downstream: PhaseContext
    ) -> None:
        spec_file = ctx_downstream.work_dir / "d5-product-spec.md"
        spec_file.write_text(
            "# D5: Product Spec\nNo recommendation keyword here.\n",
            encoding="utf-8",
        )
        result = phase.parse_output(ctx_downstream, raw="raw")
        assert result.recommendation == "implement"

    def test_extracts_park_recommendation(
        self, phase: D5Phase, ctx_upstream: PhaseContext
    ) -> None:
        brief_file = ctx_upstream.work_dir / "d5-research-brief.md"
        brief_file.write_text(
            "# D5: Research Brief\n\nFindings inconclusive.\n\npark\n",
            encoding="utf-8",
        )
        result = phase.parse_output(ctx_upstream, raw="raw")
        assert result.recommendation == "park"


# ===================================================================
# execute SUCCESS with mock – upstream
# ===================================================================


class _MockD5Phase(D5Phase):
    """D5Phase with a mocked run_claude that writes the output file."""

    def __init__(self, content: str, filename: str) -> None:
        super().__init__()
        self._content = content
        self._filename = filename

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / self._filename
        output_file.write_text(self._content, encoding="utf-8")
        return "mock-raw-output"


class TestExecuteWithMock:
    """D5Phase.execute() end-to-end with a mocked Claude adapter."""

    def test_execute_upstream_returns_success(
        self, ctx_upstream: PhaseContext
    ) -> None:
        phase = _MockD5Phase(SAMPLE_RESEARCH_BRIEF, "d5-research-brief.md")
        result = phase.execute(ctx_upstream)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.output_file == ctx_upstream.work_dir / "d5-research-brief.md"
        assert result.data.mode == "upstream"
        assert result.data.recommendation == "research"
        assert result.error is None
        assert result.duration_s > 0

    def test_execute_downstream_returns_success(
        self, ctx_downstream: PhaseContext
    ) -> None:
        phase = _MockD5Phase(SAMPLE_PRODUCT_SPEC, "d5-product-spec.md")
        result = phase.execute(ctx_downstream)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.output_file == ctx_downstream.work_dir / "d5-product-spec.md"
        assert result.data.mode == "downstream"
        assert result.data.recommendation == "implement"
        assert result.error is None
        assert result.duration_s > 0
