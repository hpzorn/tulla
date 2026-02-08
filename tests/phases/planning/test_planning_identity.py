"""Tests for PLANNING_IDENTITY in planning phase prompts."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from tulla.core.phase import PhaseContext
from tulla.phases.planning.p1 import P1Phase
from tulla.phases.planning.p2 import P2Phase
from tulla.phases.planning.p3 import P3Phase
from tulla.phases.planning.p4 import P4Phase
from tulla.phases.planning.p5 import P5Phase
from tulla.phases.planning.p6 import P6Phase


@pytest.fixture()
def ctx(tmp_path: Path) -> PhaseContext:
    return PhaseContext(
        idea_id="42",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.planning"),
    )


ALL_PHASES = [
    pytest.param(P1Phase(), id="P1"),
    pytest.param(P2Phase(), id="P2"),
    pytest.param(P3Phase(), id="P3"),
    pytest.param(P4Phase(), id="P4"),
    pytest.param(P5Phase(), id="P5"),
    pytest.param(P6Phase(), id="P6"),
]


class TestPlanningIdentity:
    """All planning phases include the shared PLANNING_IDENTITY preamble."""

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_prompt_includes_planning_tulla(self, phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Planning-Tulla" in prompt

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_prompt_includes_capabilities(self, phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "**Capabilities**" in prompt

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_prompt_includes_context_mention(self, phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "A-box" in prompt

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_identity_before_goal(self, phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        identity_pos = prompt.index("Planning-Tulla")
        goal_pos = prompt.index("## Goal")
        assert identity_pos < goal_pos
