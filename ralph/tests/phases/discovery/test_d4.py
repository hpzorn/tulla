"""Tests for tulla.phases.discovery.d4 – D4Phase."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.discovery.d4 import D4Phase

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
        logger=logging.getLogger("test.d4"),
    )


@pytest.fixture()
def phase() -> D4Phase:
    """A plain D4Phase instance."""
    return D4Phase()


SAMPLE_GAP_ANALYSIS = """\
# D4: Gap Analysis
**Idea**: idea-42
**Date**: 2026-02-01
**Time-box**: 15 minutes

## Gap Categories

### Knowledge Gaps
| Gap | Impact | Research Question |
|-----|--------|-------------------|
| Unknown scaling limits | High | "How does X scale?" |

### Technical Gaps
| Gap | Blocks | Solution Approach |
|-----|--------|-------------------|
| No API endpoint | Core feature | Build |
| Missing auth layer | Security | Integrate |

### Quality-Attribute Gaps
| Quality Attribute | Current State | Desired State | Gap Severity |
|-------------------|---------------|---------------|--------------|
| Maintainability | Low | High | High |

### Resource Gaps
| Gap | Type | Mitigation |
|-----|------|------------|
| No frontend dev | Skills | Hire/Train |

### Integration Gaps
| Gap | Systems Involved | Complexity |
|-----|------------------|------------|
| ontology-server link | ontology-server, idea-pool | Medium |

## Priority Matrix
| Gap | Value Impact | Effort to Close | Priority |
|-----|--------------|-----------------|----------|
| No API endpoint | High | Medium | P0 |
| Missing auth layer | High | Low | P0 |
| Unknown scaling limits | Medium | High | P1 |
| No frontend dev | Low | High | P2 |
| ontology-server link | Medium | Medium | P1 |

## Blockers
1. No API endpoint: blocks core functionality
2. Missing auth layer: blocks security review

## Opportunities
1. ontology-server integration: enables semantic queries
"""


# ===================================================================
# build_prompt includes idea_id
# ===================================================================


class TestBuildPrompt:
    """D4Phase.build_prompt() tests."""

    def test_includes_idea_id(self, phase: D4Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert ctx.idea_id in prompt

    def test_includes_gap_analysis_output_path(
        self, phase: D4Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "d4-gap-analysis.md" in prompt

    def test_includes_phase_heading(
        self, phase: D4Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Phase D4: Gap Analysis" in prompt

    def test_reads_d1_d2_d3(
        self, phase: D4Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "d1-inventory.md" in prompt
        assert "d2-personas.md" in prompt
        assert "d3-value-mapping.md" in prompt

    def test_includes_schema_context_when_provided(
        self, phase: D4Phase, tmp_path: Path
    ) -> None:
        ctx = PhaseContext(
            idea_id="idea-42",
            work_dir=tmp_path,
            config={"schema_context": "iSAQB quality attributes here"},
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.d4"),
        )
        prompt = phase.build_prompt(ctx)
        assert "iSAQB quality attributes here" in prompt
        assert "iSAQB Architecture Schema" in prompt

    def test_no_schema_block_when_absent(
        self, phase: D4Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "iSAQB Architecture Schema" not in prompt


# ===================================================================
# get_tools includes ontology-server
# ===================================================================


class TestGetTools:
    """D4Phase.get_tools() tests."""

    def test_includes_ontology_server_tools(
        self, phase: D4Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        tool_names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ontology" in tool_names
        assert "mcp__ontology-server__sparql_query" in tool_names

    def test_includes_read_write(
        self, phase: D4Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        tool_names = {t["name"] for t in tools}
        assert "Read" in tool_names
        assert "Write" in tool_names


# ===================================================================
# parse_output raises on missing file
# ===================================================================


class TestParseOutputMissing:
    """D4Phase.parse_output() when d4-gap-analysis.md is absent."""

    def test_raises_parse_error_on_missing_file(
        self, phase: D4Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError, match="d4-gap-analysis.md not found"):
            phase.parse_output(ctx, raw="anything")

    def test_parse_error_includes_context(
        self, phase: D4Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError) as exc_info:
            phase.parse_output(ctx, raw="raw-data")
        assert "work_dir" in exc_info.value.context


# ===================================================================
# parse_output succeeds with file
# ===================================================================


class TestParseOutputSuccess:
    """D4Phase.parse_output() when d4-gap-analysis.md is present."""

    def test_returns_d4_output(
        self, phase: D4Phase, ctx: PhaseContext
    ) -> None:
        gap_file = ctx.work_dir / "d4-gap-analysis.md"
        gap_file.write_text(SAMPLE_GAP_ANALYSIS, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.gap_analysis_file == gap_file
        assert result.gaps_found == 5
        assert result.p0_gaps == 2

    def test_zero_gaps_when_table_empty(
        self, phase: D4Phase, ctx: PhaseContext
    ) -> None:
        minimal = (
            "# D4: Gap Analysis\n"
            "## Priority Matrix\n"
            "No gaps found.\n"
            "## Blockers\n"
        )
        gap_file = ctx.work_dir / "d4-gap-analysis.md"
        gap_file.write_text(minimal, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")
        assert result.gaps_found == 0
        assert result.p0_gaps == 0


# ===================================================================
# execute SUCCESS with mock
# ===================================================================


class _MockD4Phase(D4Phase):
    """D4Phase with a mocked run_claude that writes the gap analysis file."""

    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "d4-gap-analysis.md"
        output_file.write_text(self._content, encoding="utf-8")
        return "mock-raw-output"


class TestExecuteWithMock:
    """D4Phase.execute() end-to-end with a mocked Claude adapter."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockD4Phase(SAMPLE_GAP_ANALYSIS)
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.gap_analysis_file == ctx.work_dir / "d4-gap-analysis.md"
        assert result.data.gaps_found == 5
        assert result.data.p0_gaps == 2
        assert result.error is None
        assert result.duration_s > 0
