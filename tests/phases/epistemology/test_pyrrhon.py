"""Baseline tests for SignalPhase (pre-rewrite).

These tests capture the current behavior of ``SignalPhase`` so that the
philosopher-grounded rewrite (Pyrrhonian Skepticism mode) can be validated
against a known baseline.  No prompt may be modified until these pass.

Requirement: prd:req-83-1-2
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseResult, PhaseStatus
from tulla.phases.epistemology.models import EpistemologyOutput
from tulla.phases.epistemology.signal import SignalPhase

# ---------------------------------------------------------------------------
# Sample output constant — minimal valid markdown matching Signal mode format
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Signal Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Extension, Challenge, Application

## Signal 1: Quantum computing breakthrough
**What**: IBM demonstrates 1000-qubit processor
**When**: 2026-02-10
**Strength**: strong
**Source**: https://example.com/quantum
**Pool Impact**: Validates idea-12 on post-classical computing

## Signal 2: Open-source AI regulation
**What**: EU publishes draft AI Act enforcement guidelines
**When**: 2026-02-08
**Strength**: medium
**Source**: https://example.com/regulation
**Pool Impact**: Threatens idea-7 assumptions on permissive licensing

## Signal 3: Decentralised identity standard
**What**: W3C finalises DID 2.0 specification
**When**: 2026-01-30
**Strength**: strong
**Source**: https://example.com/did
**Pool Impact**: Enables idea-19 on self-sovereign credentials

## Idea 1: Post-Classical Toolchain
**Protocol**: Extension
**Signal**: Quantum computing breakthrough
**Pool Ideas Involved**: idea-12
**Description**: Build a hybrid classical-quantum development toolkit that \
lets pool contributors prototype algorithms on the new 1000-qubit hardware. \
This bridges the gap between theoretical advantage and practical use.
**Novelty**: Concrete SDK targeting a verified qubit count, not speculative.

## Idea 2: Compliance-Aware Licensing Engine
**Protocol**: Challenge
**Signal**: Open-source AI regulation
**Pool Ideas Involved**: idea-7
**Description**: A license-selection engine that adapts to jurisdiction-specific \
AI regulation. Challenges the assumption that a single permissive license suffices.
**Novelty**: Dynamic license selection driven by regulatory geography.

## Idea 3: DID-Backed Contributor Identity
**Protocol**: Application
**Signal**: Decentralised identity standard
**Pool Ideas Involved**: idea-19
**Description**: Apply the finalised DID 2.0 spec to give each pool contributor \
a verifiable, self-sovereign identity anchored to their contributions.
**Novelty**: Uses a ratified standard rather than a bespoke identity layer.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by SignalPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = SignalPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = SignalPhase().build_prompt(ctx)
        assert "ep-signal-ideas.md" in prompt

    def test_prompt_contains_phase_marker(self, ctx: PhaseContext) -> None:
        prompt = SignalPhase().build_prompt(ctx)
        # Signal mode defines multiple phases; at least one must appear
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert found, "Prompt must contain at least one Phase marker"


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by SignalPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = SignalPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = SignalPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = SignalPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = SignalPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify SignalPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = SignalPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-signal-ideas.md", SAMPLE_OUTPUT)
        phase = SignalPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "signal"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedSignalPhase(SignalPhase):
    """SignalPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "ep-signal-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedSignalPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "signal"
