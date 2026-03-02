"""Tests for ContradictionPhase (Hegelian dialectical synthesis).

These tests verify the philosopher-grounded ``ContradictionPhase`` including
5-layer encoding (Persona, Operational Rules, Phase Markers, Output Format,
Anti-Collapse Guards) with Hegel, Aufhebung, and determinate negation grounding.

Requirement: prd:req-83-1-4, prd:req-83-3-3
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.epistemology.contradiction import ContradictionPhase
from tulla.phases.epistemology.models import EpistemologyOutput

# ---------------------------------------------------------------------------
# Sample output constant — uses Synthesis N: headings (not Idea N:)
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Contradiction Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Transcendence, Integration, Reframing

## Thesis
**Core Claim**: Structured ontology management is the optimal substrate for \
capturing creative intent in ideation workflows.
**Source**: idea 42

## Antithesis
**Core Claim**: Creative intent is fundamentally fluid and resists structural \
capture — any ontology imposed on ideation constrains more than it enables.
**Source**: idea 19
**Contradiction Test**: Both cannot be true simultaneously: if ontology is \
optimal for capturing creative intent, then creative intent is structurally \
capturable; if creative intent resists structural capture, then ontology \
cannot be optimal for it.

## Tension Analysis
**Thesis Gets Right**: Ontologies provide queryable, composable structure that \
enables automated insight surfacing impossible with unstructured notes.
**Antithesis Gets Right**: Early-stage ideation requires rapid, low-friction \
exploration that rigid schemas impede.
**Shared Error**: Both assume structure and fluidity are properties of the \
MEDIUM rather than of the PHASE — neither recognises that the same idea may \
need fluid capture early and structured representation later.
**Stakes**: Picking thesis alone produces a rigid system that discourages \
exploratory thinking; picking antithesis alone produces rich notes that cannot \
be computationally leveraged.

## Synthesis 1: Phase-Adaptive Knowledge Substrate
**Resolution Type**: Transcendence
**The Larger Whole**: A knowledge substrate that shifts its structural rigidity \
based on idea maturity — fluid at seedling, structured at sapling, formal at oak.
**From Thesis**: Queryable, ontology-backed relationships for mature ideas.
**From Antithesis**: Low-friction, schema-free capture for nascent ideas.
**Novel Contribution**: Maturity-driven structural migration — ideas graduate \
through representation tiers automatically.
**Description**: Build a substrate that starts as freeform text and \
progressively hardens into ontology-backed triples as the idea matures. The \
user never chooses a representation; the system infers readiness from usage \
patterns. This is neither unstructured nor structured — it is structuring.

## Synthesis 2: Intent-Preserving Flexible Ontology
**Resolution Type**: Integration
**Kernel from Thesis**: Typed relationships enable computational reasoning \
over idea networks.
**Kernel from Antithesis**: Creative intent carries nuance that fixed schemas \
destroy.
**New Capability**: An ontology that preserves the original intent expression \
alongside its formalisation, enabling both human re-reading and machine \
querying on the same artifact.
**Description**: Extend the ontology with an intent-preservation layer that \
stores the raw creative expression as a first-class annotation on every \
triple. Queries can traverse structure while humans can always recover the \
original phrasing. Neither pure ontology nor pure notes could do this.

## Synthesis 3: The Structuring Question
**Resolution Type**: Reframing
**False Dichotomy**: The debate presupposes that representation format is a \
design-time choice. Both sides argue about what format to BUILD rather than \
asking when and how format should EMERGE.
**Better Question**: Under what conditions does an idea's own evolution \
signal readiness for structural commitment, and how can the system detect \
those signals?
**Description**: Reframe the entire problem from "pick a representation" to \
"build a maturity detector." The contradiction dissolves because neither \
side was asking the right question — the question is not structure vs. \
fluidity but timing of structural commitment.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by ContradictionPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = ContradictionPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = ContradictionPhase().build_prompt(ctx)
        assert "ep-contradiction-ideas.md" in prompt

    def test_prompt_contains_phase_marker(self, ctx: PhaseContext) -> None:
        prompt = ContradictionPhase().build_prompt(ctx)
        # Contradiction mode defines 5 phases; at least one must appear
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert found, "Prompt must contain at least one Phase marker"

    def test_prompt_contains_hegel_grounding(self, ctx: PhaseContext) -> None:
        prompt = ContradictionPhase().build_prompt(ctx)
        assert "Hegel" in prompt
        assert "Aufhebung" in prompt
        assert "determinate negation" in prompt

    def test_prompt_contains_anti_collapse_guards(self, ctx: PhaseContext) -> None:
        prompt = ContradictionPhase().build_prompt(ctx)
        assert "Anti-Collapse Guards" in prompt
        assert "Do NOT argue one side only" in prompt
        assert "Do NOT produce synthesis that says" in prompt
        assert "NEITHER thesis nor antithesis contained" in prompt
        assert "why the opposition existed" in prompt
        assert "impossible to arrive at by simply averaging" in prompt

    def test_prompt_contains_operational_rules(self, ctx: PhaseContext) -> None:
        prompt = ContradictionPhase().build_prompt(ctx)
        assert "Operational Rules" in prompt
        assert "AUFHEBUNG CRITERION" in prompt
        assert "IDENTIFY THE SHARED ERROR" in prompt

    def test_prompt_contains_aufhebung_verification(self, ctx: PhaseContext) -> None:
        prompt = ContradictionPhase().build_prompt(ctx)
        assert "verify the Aufhebung criterion" in prompt


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by ContradictionPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = ContradictionPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = ContradictionPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = ContradictionPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = ContradictionPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify ContradictionPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = ContradictionPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-contradiction-ideas.md", SAMPLE_OUTPUT)
        phase = ContradictionPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "contradiction"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedContradictionPhase(ContradictionPhase):
    """ContradictionPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]) -> Any:
        output_file = ctx.work_dir / "ep-contradiction-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedContradictionPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "contradiction"
