"""Baseline tests for PoolPhase (pre-rewrite).

These tests capture the current behavior of ``PoolPhase`` so that the
philosopher-grounded rewrite (Baconian inductive mode) can be
validated against a known baseline.  No prompt may be modified until these pass.

Requirement: prd:req-83-1-7
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseResult, PhaseStatus
from tulla.phases.epistemology.models import EpistemologyOutput
from tulla.phases.epistemology.pool import PoolPhase

# ---------------------------------------------------------------------------
# Sample output constant — uses Idea N: headings with Pool mode format
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Pool Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Gap Analysis, Conceptual Combination, Assumption Inversion

## Pool Landscape
### Clusters
**Semantic Infrastructure**: idea-11 (ontology server), idea-17 (ADR linking), \
idea-31 (graph RAG)
**Epistemology Modes**: idea-42 (pool cartography), idea-44 (signal detection), \
idea-51 (contradiction mining)
**Developer Experience**: idea-22 (CLI tooling), idea-28 (prompt templates), \
idea-33 (auto-documentation)
**Evaluation**: idea-55 (rubric scoring), idea-58 (mode distinctness metrics)

### Gaps
1. No connection between Evaluation and Semantic Infrastructure — metrics \
are not stored in the knowledge graph.
2. Developer Experience cluster has no link to Epistemology Modes — prompt \
authoring is disconnected from mode design.
3. No idea addresses cross-mode synthesis — combining outputs from multiple \
epistemology runs.

### Shared Assumptions
1. Single-idea-in, ideas-out: idea-42, idea-44, idea-51, idea-55 all assume \
one root idea produces a fixed number of outputs.
2. Text-only output: idea-28, idea-33, idea-42 assume markdown is the only \
output format.
3. Human-triggered runs: idea-22, idea-42, idea-44 assume a human initiates \
each epistemology run.

## Root Selection
**Selected Root**: idea-42 (pool cartography)
**Rationale**: idea-42 sits at the intersection of two major gaps — it belongs \
to Epistemology Modes but its cartographic nature makes it a natural bridge to \
Evaluation (map quality is measurable) and Semantic Infrastructure (the map \
could be persisted as a knowledge graph subgraph).

## Idea 1: Metric-Enriched Knowledge Graph
**Protocol**: Gap Analysis
**Gap Addressed**: Gap 1 — Evaluation disconnected from Semantic Infrastructure
**Clusters Bridged**: Evaluation ↔ Semantic Infrastructure
**Description**: Store evaluation metrics (rubric scores, mode distinctness \
coefficients) as first-class triples in the ontology server. This allows \
SPARQL queries like "which modes scored below threshold on Contradiction \
Handling?" and enables the pool map to include evaluation health per cluster.

## Idea 2: Mode-Aware Prompt Workbench
**Protocol**: Conceptual Combination
**Parent Ideas**: idea-28 (prompt templates) from Developer Experience + \
idea-42 (pool cartography) from Epistemology Modes
**From idea-28**: Structured prompt template system with variables and previews
**From idea-42**: Cartographic analysis that reveals pool structure and gaps
**Description**: Build a prompt authoring tool that understands epistemology \
mode structure. When editing a mode prompt, the workbench shows which pool \
clusters the mode tends to generate into, which gaps it has never addressed, \
and which anti-collapse guards are active. Prompt authoring becomes \
pool-topology-aware.

## Idea 3: Autonomous Pool Maintenance
**Protocol**: Assumption Inversion
**Assumption Challenged**: "Human-triggered runs" — assumption 3 from census
**Ideas Affected**: idea-22 (CLI tooling), idea-42 (pool cartography), \
idea-44 (signal detection)
**Description**: Invert the assumption that a human must initiate each \
epistemology run. Instead, let the pool map itself trigger runs: when the \
cartographic analysis detects a gap exceeding a staleness threshold or a \
cluster falling below a diversity minimum, it autonomously queues the most \
appropriate mode to address the deficit. The pool becomes self-maintaining.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by PoolPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = PoolPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = PoolPhase().build_prompt(ctx)
        assert "ep-pool-ideas.md" in prompt

    def test_prompt_contains_phase_marker(self, ctx: PhaseContext) -> None:
        prompt = PoolPhase().build_prompt(ctx)
        # Pool mode defines 5 phases; at least one must appear
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert found, "Prompt must contain at least one Phase marker"

    def test_prompt_contains_pool_cartography_emphasis(self, ctx: PhaseContext) -> None:
        prompt = PoolPhase().build_prompt(ctx)
        # Pool mode is distinctively cartographic — mapping the pool is the core
        assert "Pool Mode" in prompt


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by PoolPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = PoolPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = PoolPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = PoolPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = PoolPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify PoolPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = PoolPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-pool-ideas.md", SAMPLE_OUTPUT)
        phase = PoolPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "pool"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedPoolPhase(PoolPhase):
    """PoolPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "ep-pool-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedPoolPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "pool"
