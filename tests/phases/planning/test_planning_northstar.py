"""Tests for northstar injection in planning phase prompts."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from tulla.core.phase import PhaseContext
from tulla.phases.planning import build_northstar_section
from tulla.phases.planning.p1 import P1Phase
from tulla.phases.planning.p2 import P2Phase
from tulla.phases.planning.p3 import P3Phase
from tulla.phases.planning.p4 import P4Phase
from tulla.phases.planning.p5 import P5Phase
from tulla.phases.planning.p6 import P6Phase


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
        "object": "plan",
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
            "d5": {"northstar": "An idea management agent.", "recommendation": "plan"},
        }
        result = build_northstar_section(grouped)
        assert "## Northstar" in result
        assert "An idea management agent." in result

    def test_returns_empty_when_no_d5(self) -> None:
        grouped = {"d1": {"tools_found": 5}}
        assert build_northstar_section(grouped) == ""

    def test_returns_empty_when_northstar_empty(self) -> None:
        grouped = {"d5": {"northstar": "", "recommendation": "plan"}}
        assert build_northstar_section(grouped) == ""

    def test_returns_empty_when_no_facts(self) -> None:
        assert build_northstar_section({}) == ""


# ---------------------------------------------------------------------------
# Integration tests: northstar appears in all planning phase prompts
# ---------------------------------------------------------------------------

ALL_PHASES = [
    pytest.param(P1Phase(), id="P1"),
    pytest.param(P2Phase(), id="P2"),
    pytest.param(P3Phase(), id="P3"),
    pytest.param(P4Phase(), id="P4"),
    pytest.param(P5Phase(), id="P5"),
    pytest.param(P6Phase(), id="P6"),
]


def _ctx_with_northstar(tmp_path: Path) -> PhaseContext:
    return PhaseContext(
        idea_id="42",
        work_dir=tmp_path,
        config={"upstream_facts": NORTHSTAR_TRIPLES},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.planning"),
    )


def _ctx_without_northstar(tmp_path: Path) -> PhaseContext:
    return PhaseContext(
        idea_id="42",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.planning"),
    )


class TestNorthstarInPrompts:
    """Northstar section appears in all planning phase prompts when D5 facts present."""

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


class TestUpstreamFactsInPrompts:
    """Upstream facts section appears in all planning phase prompts when facts present."""

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_upstream_facts_section_present(self, phase, tmp_path: Path) -> None:
        ctx = _ctx_with_northstar(tmp_path)
        prompt = phase.build_prompt(ctx)
        assert "## Upstream Facts" in prompt

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_upstream_facts_contain_field_names(self, phase, tmp_path: Path) -> None:
        ctx = _ctx_with_northstar(tmp_path)
        prompt = phase.build_prompt(ctx)
        assert "tools_found" in prompt

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_upstream_facts_before_goal(self, phase, tmp_path: Path) -> None:
        ctx = _ctx_with_northstar(tmp_path)
        prompt = phase.build_prompt(ctx)
        facts_pos = prompt.index("## Upstream Facts")
        goal_pos = prompt.index("## Goal")
        assert facts_pos < goal_pos


class TestUpstreamFactsOmitted:
    """No upstream facts section when none are provided."""

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_no_upstream_facts_section(self, phase, tmp_path: Path) -> None:
        ctx = _ctx_without_northstar(tmp_path)
        prompt = phase.build_prompt(ctx)
        assert "## Upstream Facts" not in prompt
