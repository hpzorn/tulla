"""Baseline tests for AutoPhase (pre-rewrite).

These tests capture the current behavior of ``AutoPhase`` so that the
philosopher-grounded rewrite can be validated against a known baseline.
No prompt may be modified until these pass.

Requirement: prd:req-83-1-8
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseResult, PhaseStatus
from tulla.phases.epistemology.auto import AutoPhase
from tulla.phases.epistemology.models import EpistemologyOutput

# ---------------------------------------------------------------------------
# Sample output constant — Auto mode generates 12 ideas (4 frameworks x 3)
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Auto Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Extension, Assumption Inversion, Gap Analysis, Conceptual Combination

## Diagnosis
| Dimension | Assessment | Evidence |
|-----------|-----------|----------|
| Maturity | sapling | Has structure (5-layer encoding) but gaps in evaluation |
| Connectivity | connected | 3 neighbours: idea-11, idea-17, idea-31 |
| Assumption Load | heavy | Assumes single-mode runs, text-only output, human trigger |
| Decomposability | compound | Separable into prompt engineering + evaluation + selection |
| Domain Specificity | bridging | Touches epistemology and software engineering |

## Framework Prescription
| Framework | Qualifying Rule | Diagnostic Basis |
|-----------|----------------|------------------|
| Extension | maturity >= sapling | Sapling with clear growth direction |
| Assumption Inversion | assumption load >= heavy | 3 heavy assumptions identified |
| Gap Analysis | connectivity <= connected | 3 neighbours, gaps visible |
| Conceptual Combination | cross-domain access | Bridging two domains |

## Idea 1: Layered Prompt Compiler
**Protocol**: Extension
**Diagnostic Basis**: Maturity — sapling with 5-layer structure
**Source Ideas**: idea-42
**Description**: Push the 5-layer encoding from a manual pattern into a \
compiled representation. A prompt compiler takes layers as structured input \
and produces optimised single-string prompts with guaranteed guard placement.
**Novelty**: Moves from pattern documentation to tooling.

## Idea 2: Adaptive Layer Weighting
**Protocol**: Extension
**Diagnostic Basis**: Maturity — structure exists but gaps in evaluation
**Source Ideas**: idea-42, idea-55
**Description**: Extend the 5-layer pattern with per-layer importance weights \
that adjust based on evaluation feedback. Layers that correlate with higher \
rubric scores get amplified in subsequent runs.
**Novelty**: Makes the encoding adaptive rather than static.

## Idea 3: Cross-Mode Layer Sharing
**Protocol**: Extension
**Diagnostic Basis**: Maturity — sapling ready for growth
**Source Ideas**: idea-42, idea-44, idea-51
**Description**: Enable modes to share individual layers (e.g., reuse the same \
Anti-Collapse Guard layer across Socratic and Hegelian modes while keeping \
distinct Persona layers). Reduces prompt maintenance burden.
**Novelty**: Layer-level modularity rather than whole-prompt copying.

## Idea 4: Assumption-Free Epistemology
**Protocol**: Assumption Inversion
**Diagnostic Basis**: Assumption Load — assumes single-mode runs
**Source Ideas**: idea-42
**Description**: Invert the single-mode assumption entirely. Instead of running \
one mode per session, run all qualifying modes in parallel and let their outputs \
compete. The pool map becomes a tournament bracket.
**Novelty**: Multi-mode execution as the default, not the exception.

## Idea 5: Visual Output Epistemology
**Protocol**: Assumption Inversion
**Diagnostic Basis**: Assumption Load — assumes text-only output
**Source Ideas**: idea-42, idea-28
**Description**: Invert the text-only assumption. Each mode produces a visual \
artefact (graph, diagram, map) as its primary output, with text as annotation. \
The pool map becomes literally visual.
**Novelty**: Non-textual primary outputs for epistemology modes.

## Idea 6: Continuous Background Epistemology
**Protocol**: Assumption Inversion
**Diagnostic Basis**: Assumption Load — assumes human-triggered runs
**Source Ideas**: idea-42, idea-22
**Description**: Invert human-triggered execution. Modes run continuously in the \
background, watching for changes in the knowledge graph that match their trigger \
conditions. New ideas appear autonomously when conditions are met.
**Novelty**: Event-driven rather than request-driven epistemology.

## Idea 7: Evaluation Bridge
**Protocol**: Gap Analysis
**Diagnostic Basis**: Connectivity — gap between evaluation and epistemology
**Source Ideas**: idea-42, idea-55
**Description**: Bridge the gap between epistemology modes and evaluation metrics. \
Each mode run automatically produces a self-assessment using the 6-dimension \
rubric, stored as triples in the knowledge graph alongside the generated ideas.
**Novelty**: Closes evaluation-epistemology gap at the mode level.

## Idea 8: Infrastructure Feedback Loop
**Protocol**: Gap Analysis
**Diagnostic Basis**: Connectivity — no link from infrastructure to modes
**Source Ideas**: idea-42, idea-11
**Description**: Create a feedback channel from semantic infrastructure back to \
epistemology modes. When the ontology server detects structural patterns (orphan \
nodes, dense clusters, missing relations), it surfaces these as mode inputs.
**Novelty**: Infrastructure becomes an active participant in ideation.

## Idea 9: Developer Experience for Mode Authors
**Protocol**: Gap Analysis
**Diagnostic Basis**: Connectivity — DX cluster disconnected from modes
**Source Ideas**: idea-42, idea-22, idea-28
**Description**: Fill the gap between developer experience tooling and mode \
authoring. Build a mode development kit with prompt preview, guard validation, \
and rubric pre-scoring before deployment.
**Novelty**: First-class authoring tools for epistemology modes.

## Idea 10: Ontology-Guided Ideation
**Protocol**: Conceptual Combination
**Diagnostic Basis**: Domain Specificity — bridging epistemology and software
**Source Ideas**: idea-42, idea-11
**Description**: Combine the ontology server's structural knowledge with \
epistemology mode selection. The auto-selector reads the knowledge graph's \
topology to determine which mode would be most productive for a given idea, \
replacing the current generic diagnostic dimensions.
**Novelty**: Topology-driven mode selection grounded in actual graph structure.

## Idea 11: Rubric-Driven Prompt Evolution
**Protocol**: Conceptual Combination
**Diagnostic Basis**: Domain Specificity — bridging evaluation and prompt design
**Source Ideas**: idea-42, idea-55, idea-58
**Description**: Combine rubric scoring with prompt engineering. After each mode \
run, the 6-dimension rubric scores feed into an evolution algorithm that mutates \
the prompt layers to maximise distinctness and quality scores.
**Novelty**: Automated prompt improvement via evaluation feedback.

## Idea 12: Cross-Domain Pattern Mining
**Protocol**: Conceptual Combination
**Diagnostic Basis**: Domain Specificity — bridging two domains
**Source Ideas**: idea-42, idea-31
**Description**: Combine graph RAG capabilities with epistemology pattern \
detection. Mine the knowledge graph for recurring structural patterns across \
domains and use them as seeds for new epistemology modes.
**Novelty**: Graph structure as epistemology mode generator.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by AutoPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "ep-auto-ideas.md" in prompt

    def test_prompt_contains_phase_marker(self, ctx: PhaseContext) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        # Auto mode defines 5 phases; at least one must appear
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert found, "Prompt must contain at least one Phase marker"

    def test_prompt_contains_auto_mode_identity(self, ctx: PhaseContext) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "Auto Mode" in prompt

    def test_timeout_is_1200(self) -> None:
        phase = AutoPhase()
        assert phase.timeout_s == 1200.0


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by AutoPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = AutoPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = AutoPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_get_related_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = AutoPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_related_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = AutoPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = AutoPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify AutoPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = AutoPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-auto-ideas.md", SAMPLE_OUTPUT)
        phase = AutoPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 12
        assert result.mode == "auto"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedAutoPhase(AutoPhase):
    """AutoPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "ep-auto-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedAutoPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 12
        assert result.data.mode == "auto"
