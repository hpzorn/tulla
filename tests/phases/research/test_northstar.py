"""Tests for northstar injection in research phase prompts."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from tulla.core.phase import PhaseContext
from tulla.phases.research import build_northstar_section
from tulla.phases.research.r1 import R1Phase
from tulla.phases.research.r2 import R2Phase
from tulla.phases.research.r3 import R3Phase
from tulla.phases.research.r4 import R4Phase
from tulla.phases.research.r5 import R5Phase
from tulla.phases.research.r6 import R6Phase

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

PHASE_NS = "http://tulla.dev/phase#"

NORTHSTAR_TRIPLES = [
    {
        "subject": f"{PHASE_NS}42-d5",
        "predicate": f"{PHASE_NS}preserves-northstar",
        "object": "A CLI agent that manages idea lifecycles through ontology-driven phases.",
    },
    {
        "subject": f"{PHASE_NS}42-d5",
        "predicate": f"{PHASE_NS}preserves-recommendation",
        "object": "research",
    },
    {
        "subject": f"{PHASE_NS}42-d1",
        "predicate": f"{PHASE_NS}preserves-tools_found",
        "object": "5",
    },
]


# ---------------------------------------------------------------------------
# Unit tests for build_northstar_section
# ---------------------------------------------------------------------------


class TestBuildNorthstarSection:
    """Tests for the build_northstar_section helper."""

    def test_renders_northstar_when_present(self) -> None:
        grouped = {
            "d5": {"northstar": "An idea management agent.", "recommendation": "research"},
        }
        result = build_northstar_section(grouped)
        assert "## Northstar" in result
        assert "An idea management agent." in result

    def test_returns_empty_when_no_d5(self) -> None:
        grouped = {"d1": {"tools_found": 5}}
        assert build_northstar_section(grouped) == ""

    def test_returns_empty_when_northstar_empty(self) -> None:
        grouped = {"d5": {"northstar": "", "recommendation": "research"}}
        assert build_northstar_section(grouped) == ""

    def test_returns_empty_when_no_facts(self) -> None:
        assert build_northstar_section({}) == ""


# ---------------------------------------------------------------------------
# Integration tests: northstar appears in all research phase prompts
# ---------------------------------------------------------------------------

ALL_PHASES = [
    pytest.param(R1Phase(), id="R1"),
    pytest.param(R2Phase(), id="R2"),
    pytest.param(R3Phase(), id="R3"),
    pytest.param(R4Phase(), id="R4"),
    pytest.param(R5Phase(), id="R5"),
    pytest.param(R6Phase(), id="R6"),
]


def _ctx_with_northstar(tmp_path: Path) -> PhaseContext:
    return PhaseContext(
        idea_id="42",
        work_dir=tmp_path,
        config={"upstream_facts": NORTHSTAR_TRIPLES},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.research"),
    )


def _ctx_without_northstar(tmp_path: Path) -> PhaseContext:
    return PhaseContext(
        idea_id="42",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.research"),
    )


class TestNorthstarInPrompts:
    """Northstar section appears in all research phase prompts when D5 facts present."""

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_northstar_section_present(self, phase, tmp_path: Path) -> None:
        ctx = _ctx_with_northstar(tmp_path)
        prompt = phase.build_prompt(ctx)
        assert "## Northstar" in prompt
        assert "ontology-driven phases" in prompt

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_northstar_before_goal(self, phase, tmp_path: Path) -> None:
        ctx = _ctx_with_northstar(tmp_path)
        prompt = phase.build_prompt(ctx)
        ns_pos = prompt.index("## Northstar")
        goal_pos = prompt.index("## Goal")
        assert ns_pos < goal_pos


class TestNorthstarOmitted:
    """No northstar section when D5 facts are absent."""

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_no_northstar_when_no_facts(self, phase, tmp_path: Path) -> None:
        ctx = _ctx_without_northstar(tmp_path)
        prompt = phase.build_prompt(ctx)
        assert "## Northstar" not in prompt
