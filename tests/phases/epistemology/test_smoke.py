"""Smoke test for all 9 philosopher-grounded epistemology modes.

Verifies that every mode:
1. Instantiates without error
2. Produces a prompt containing the idea ID and an anti-collapse guard
3. Returns at least the core MCP tools
4. Parses sample output into a valid EpistemologyOutput
5. Full execute() cycle works with a mock Claude

Also verifies CLI registration covers all modes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import PhaseContext, PhaseStatus
from tulla.phases.epistemology._helpers import count_idea_headings
from tulla.phases.epistemology.models import EpistemologyOutput

# ---------------------------------------------------------------------------
# Mode registry: (cli_key, module, class_name, mode_name, output_file)
# ---------------------------------------------------------------------------

_MODES = [
    ("auto", "tulla.phases.epistemology.auto", "AutoPhase", "auto", "ep-auto-ideas.md"),
    ("pyrrhon", "tulla.phases.epistemology.signal", "PyrrhonPhase", "pyrrhon", "ep-pyrrhon-ideas.md"),
    ("aristotle", "tulla.phases.epistemology.idea", "AristotlePhase", "aristotle", "ep-aristotle-ideas.md"),
    ("hegel", "tulla.phases.epistemology.contradiction", "ContradictionPhase", "contradiction", "ep-contradiction-ideas.md"),
    ("abduction", "tulla.phases.epistemology.abduction", "AbductionPhase", "abduction", "ep-abduction-ideas.md"),
    ("dewey", "tulla.phases.epistemology.problem", "DeweyPhase", "dewey", "ep-dewey-ideas.md"),
    ("popper", "tulla.phases.epistemology.domain", "PopperPhase", "popper", "ep-popper-ideas.md"),
    ("bacon", "tulla.phases.epistemology.pool", "BaconPhase", "bacon", "ep-bacon-ideas.md"),
    ("catuskoti", "tulla.phases.epistemology.catuskoti", "CatuskotiPhase", "catuskoti", "ep-catuskoti-ideas.md"),
]


def _import_phase(module_path: str, class_name: str):
    """Dynamically import a phase class."""
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


SAMPLE_MD = """\
# Generated Ideas — {mode} Mode
**Root Idea**: {idea_id}
**Date**: 2026-02-16
**Frameworks**: Framework A, Framework B

## Idea 1: First test idea
**Description**: Smoke test idea one.

## Idea 2: Second test idea
**Description**: Smoke test idea two.

## Idea 3: Third test idea
**Description**: Smoke test idea three.
"""


@pytest.fixture()
def ctx(tmp_path: Path) -> PhaseContext:
    return PhaseContext(
        idea_id="idea-99",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.smoke"),
    )


# ---------------------------------------------------------------------------
# Parametrised tests across all 9 modes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cli_key,module_path,class_name,mode_name,output_file",
    _MODES,
    ids=[m[0] for m in _MODES],
)
class TestAllModes:
    """Smoke tests applied to every epistemology mode."""

    def test_instantiate(self, cli_key, module_path, class_name, mode_name, output_file):
        cls = _import_phase(module_path, class_name)
        phase = cls()
        assert phase is not None

    def test_build_prompt_contains_idea_id(
        self, ctx, cli_key, module_path, class_name, mode_name, output_file,
    ):
        cls = _import_phase(module_path, class_name)
        prompt = cls().build_prompt(ctx)
        assert "idea-99" in prompt

    def test_build_prompt_has_anti_collapse_guard(
        self, ctx, cli_key, module_path, class_name, mode_name, output_file,
    ):
        cls = _import_phase(module_path, class_name)
        prompt = cls().build_prompt(ctx)
        assert "Do NOT" in prompt, f"{class_name} prompt missing anti-collapse guard"

    def test_get_tools_includes_core_mcp(
        self, ctx, cli_key, module_path, class_name, mode_name, output_file,
    ):
        cls = _import_phase(module_path, class_name)
        tools = cls().get_tools(ctx)
        names = {t["name"] for t in tools}
        assert "mcp__ontology-server__get_idea" in names
        assert "Write" in names

    def test_parse_output_with_sample(
        self, ctx, cli_key, module_path, class_name, mode_name, output_file,
    ):
        content = SAMPLE_MD.format(mode=mode_name, idea_id="idea-99")
        (ctx.work_dir / output_file).write_text(content, encoding="utf-8")

        cls = _import_phase(module_path, class_name)
        result = cls().parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == mode_name

    def test_execute_mock_succeeds(
        self, ctx, cli_key, module_path, class_name, mode_name, output_file,
    ):
        cls = _import_phase(module_path, class_name)
        content = SAMPLE_MD.format(mode=mode_name, idea_id="idea-99")

        class _Mocked(cls):
            def run_claude(self, ctx, prompt, tools):
                (ctx.work_dir / output_file).write_text(content, encoding="utf-8")
                return "mock"

        result = _Mocked().execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.ideas_generated == 3


# ---------------------------------------------------------------------------
# CLI registration completeness
# ---------------------------------------------------------------------------


class TestCLIRegistration:
    """Verify that _build_ep_modes() covers all 9 modes."""

    def test_all_modes_registered(self):
        from tulla.cli import ep_modes

        expected_keys = {m[0] for m in _MODES}
        assert set(ep_modes.keys()) == expected_keys

    def test_each_mode_has_phase_id_and_instance(self):
        from tulla.cli import ep_modes

        for key, (phase_id, phase_instance) in ep_modes.items():
            assert phase_id.startswith("ep-"), f"{key}: phase_id should start with 'ep-'"
            assert hasattr(phase_instance, "build_prompt"), f"{key}: missing build_prompt"
            assert hasattr(phase_instance, "execute"), f"{key}: missing execute"
