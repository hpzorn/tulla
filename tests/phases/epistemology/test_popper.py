"""Baseline tests for PopperPhase (post-rewrite).

These tests verify the Popperian falsificationist mode — ``PopperPhase`` —
produces a prompt grounded in Popper's tradition and correctly parses output.

Requirement: prd:req-83-3-5
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.epistemology.domain import PopperPhase
from tulla.phases.epistemology.models import EpistemologyOutput

# ---------------------------------------------------------------------------
# Sample output constant — uses Idea N: headings with Popper mode format
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Popper Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Bold Conjecture, Severe Test, Error Elimination

## Bold Conjecture
Any software architecture decision record (ADR) can be automatically validated \
against the running system's topology within 5 seconds, and at least 80% of \
architectural drift would be caught by such validation before the next release.

## Testable Predictions
| # | Prediction | Conditions | Measurable Outcome |
|---|------------|------------|---------------------|
| 1 | ADR constraints formalizable as graph queries | 50 ADRs | 40+ as SPARQL |
| 2 | Topology accessible < 5s latency | > 20 services | Response < 5s |
| 3 | Drift detection > 80% | 10 violation scenarios | 8+ detected |

## Severe Tests
### Test 1: ADR Formalization Failure
**Designed to Break**: The assumption that natural-language ADRs can be reliably \
converted to executable constraints
**Method**: Take 50 ADRs from the adr-tools GitHub repository, attempt to \
formalize each as a graph query. Count failures.
**Evidence Found**: Auer et al. (2025) showed that only 62% of ADRs contain \
sufficiently precise language for automated extraction — below the 80% threshold.

### Test 2: Topology Latency Wall
**Designed to Break**: The 5-second latency assumption for real production systems
**Method**: Query topology APIs of 5 open-source microservice benchmarks \
(Sock Shop, Hipster Shop, etc.) and measure response times.
**Evidence Found**: Kubernetes API server responses for namespace-wide resource \
listing average 8-12 seconds for clusters with > 100 pods.

### Test 3: Drift Detection Coverage
**Designed to Break**: The 80% detection rate assumption
**Method**: Create 10 specific architectural violations (wrong service \
communication patterns, unauthorized database access, etc.) and test detection.
**Evidence Found**: Netflix's architectural fitness functions paper reports \
73% detection for structural violations but only 41% for behavioral ones.

## Error Elimination
| # | Prediction | Result | Explanation |
|---|------------|--------|-------------|
| 1 | ADR formalization | Falsified | Only 62% of ADRs precise enough |
| 2 | Topology latency | Falsified | Real systems exceed 5s for topology |
| 3 | Drift detection rate | Falsified | Behavioral violations below 80% |

## Improved Conjectures
The falsification reveals that the real problem is not "can we validate ADRs \
against topology" but "which ADRs are validatable and what subset of drift is \
detectable." The structure is in the BOUNDARY between formalizable and \
non-formalizable decisions.

## Idea 1: ADR Formalizability Classifier
**Framework**: Error Elimination
**From Falsification**: Prediction 1 broke — only 62% of ADRs are formalizable. \
The boundary between formalizable and non-formalizable ADRs is itself valuable.
**Description**: Build a classifier that scores ADRs on formalizability at \
write-time, nudging authors toward more precise language. The 38% that fail \
formalization reveal what kinds of architectural decisions resist automation — \
a taxonomy more valuable than the validation itself.

## Idea 2: Incremental Topology Snapshots
**Framework**: Severe Test
**From Falsification**: Prediction 2 broke on full topology queries. But drift \
detection doesn't need the FULL topology — only the delta since last check.
**Description**: Replace full topology queries with event-driven incremental \
snapshots. Subscribe to Kubernetes watch APIs for topology-relevant changes \
only. This sidesteps the latency wall by never querying the full state — \
only the changes that could indicate drift.

## Idea 3: Behavioral Drift Probes
**Framework**: Bold Conjecture
**From Falsification**: Prediction 3 broke specifically on behavioral violations \
(41% detection vs 73% structural). The gap between structural and behavioral \
detection is the real frontier.
**Description**: Design active probes that inject synthetic requests to detect \
behavioral drift (unauthorized communication paths, unexpected latency patterns). \
Structural violations are the easy problem; behavioral drift is where \
architectural erosion actually happens in production.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by PopperPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = PopperPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = PopperPhase().build_prompt(ctx)
        assert "ep-popper-ideas.md" in prompt

    def test_prompt_contains_phase_markers(self, ctx: PhaseContext) -> None:
        prompt = PopperPhase().build_prompt(ctx)
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5",
            "Phase 6",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert len(found) == 6, "Prompt must contain all 6 Phase markers"

    def test_prompt_contains_popper(self, ctx: PhaseContext) -> None:
        prompt = PopperPhase().build_prompt(ctx)
        assert "Popper" in prompt

    def test_prompt_contains_refute(self, ctx: PhaseContext) -> None:
        prompt = PopperPhase().build_prompt(ctx)
        assert "REFUTE" in prompt

    def test_prompt_contains_do_not_confirm(self, ctx: PhaseContext) -> None:
        prompt = PopperPhase().build_prompt(ctx)
        # Anti-collapse guard: "do NOT confirm" (via "confirmation bias")
        assert "confirm" in prompt.lower()

    def test_prompt_contains_p1_tt_ee_p2_cycle(self, ctx: PhaseContext) -> None:
        prompt = PopperPhase().build_prompt(ctx)
        assert "P1" in prompt
        assert "TT" in prompt
        assert "EE" in prompt
        assert "P2" in prompt

    def test_prompt_contains_bold_conjecture_framework(self, ctx: PhaseContext) -> None:
        prompt = PopperPhase().build_prompt(ctx)
        assert "Bold Conjecture" in prompt

    def test_prompt_contains_severe_test_framework(self, ctx: PhaseContext) -> None:
        prompt = PopperPhase().build_prompt(ctx)
        assert "Severe Test" in prompt

    def test_prompt_contains_error_elimination_framework(self, ctx: PhaseContext) -> None:
        prompt = PopperPhase().build_prompt(ctx)
        assert "Error Elimination" in prompt

    def test_prompt_contains_anticollapse_guards(self, ctx: PhaseContext) -> None:
        prompt = PopperPhase().build_prompt(ctx)
        assert "Anti-Collapse Guards" in prompt
        assert "BREAK" in prompt

    def test_phase_id_is_ep_popper(self) -> None:
        phase = PopperPhase()
        assert phase.phase_id == "ep-popper"


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by PopperPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = PopperPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = PopperPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = PopperPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_web_search_tool_present(self, ctx: PhaseContext) -> None:
        tools = PopperPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "WebSearch" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = PopperPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify PopperPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = PopperPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-popper-ideas.md", SAMPLE_OUTPUT)
        phase = PopperPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "popper"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedPopperPhase(PopperPhase):
    """PopperPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]) -> Any:
        output_file = ctx.work_dir / "ep-popper-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedPopperPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "popper"
