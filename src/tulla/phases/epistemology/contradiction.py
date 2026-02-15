"""Epistemology Contradiction mode — Hegelian dialectical synthesis.

The contradiction mode's distinctive process is *dialectical*: it cannot
begin until a genuine thesis-antithesis pair is established.  Finding the
real contradiction is HARDER than synthesising it — most apparent
contradictions dissolve under scrutiny into mere differences of emphasis.
The mode must prove the contradiction is real before attempting resolution.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = ["Transcendence", "Integration", "Reframing"]
_OUTPUT_FILE = "ep-contradiction-ideas.md"


class ContradictionPhase(Phase[EpistemologyOutput]):
    """Epistemology contradiction mode: find real contradictions, then synthesise."""

    phase_id: str = "ep-contradiction"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Contradiction Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your job is DIALECTICAL SYNTHESIS in the Hegelian tradition. This is\n"
            "the hardest mode because it requires finding GENUINE contradictions —\n"
            "not just differences of opinion — and producing syntheses that create\n"
            "something NEITHER side had.\n"
            "\n"
            "## CRITICAL WARNING\n"
            "Avoid 'agreeable synthesis' that just says 'do both' or 'find a balance'.\n"
            "True synthesis transcends the opposition. A valid synthesis must:\n"
            "- Produce a concept that NEITHER thesis nor antithesis contained\n"
            "- Explain why the opposition existed (what error both sides shared)\n"
            "- Be impossible to arrive at by simply averaging the two positions\n"
            "If you cannot achieve this, say so honestly. A failed synthesis attempt\n"
            "is more valuable than a fake one.\n"
            "\n"
            "## Phase 1: Establish the Thesis\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            "2. State the idea's CORE CLAIM — not a summary, but the single\n"
            "   proposition that, if false, would collapse the entire idea.\n"
            "   This is your thesis.\n"
            "\n"
            "## Phase 2: Hunt for Antitheses\n"
            "\n"
            "3. Query the pool: mcp__ontology-server__query_ideas\n"
            "4. For each pool idea, ask: does this CONTRADICT the thesis?\n"
            "   Not 'disagree' or 'take a different approach' — genuinely\n"
            "   contradict, such that both cannot be true simultaneously.\n"
            "\n"
            "   For each candidate antithesis, test it:\n"
            "   - State both propositions side by side\n"
            "   - Can both be true? If yes → not a real contradiction, discard\n"
            "   - Is the conflict about definitions? If yes → terminological, not substantive\n"
            "   - Is one simply more specific than the other? If yes → not a contradiction\n"
            "\n"
            "5. Select the STRONGEST antithesis — the one that most fundamentally\n"
            "   challenges the thesis. If no genuine antithesis exists in the pool,\n"
            "   construct the strongest possible counter-position and state that\n"
            "   you constructed it (don't pretend the pool contains it).\n"
            "\n"
            "## Phase 3: Analyse the Tension\n"
            "\n"
            "6. For the thesis-antithesis pair, work through:\n"
            "   - **What the thesis gets right** that the antithesis misses\n"
            "   - **What the antithesis gets right** that the thesis misses\n"
            "   - **The shared error**: what assumption do BOTH sides make that\n"
            "     enables the contradiction to exist?\n"
            "   - **The stakes**: what is lost if we simply pick one side?\n"
            "\n"
            "## Phase 4: Synthesise\n"
            "\n"
            "Generate exactly 3 synthesis ideas, each using a different resolution:\n"
            "\n"
            "**Transcendence**: Rise above the opposition entirely. Find a vantage\n"
            "point from which both thesis and antithesis are partial truths of a\n"
            "larger whole. The larger whole must be nameable — what IS it?\n"
            "\n"
            "**Integration**: Identify the valid kernel in each position and weave\n"
            "them into a new framework. The framework must do something neither\n"
            "position could do alone — state what that capability is.\n"
            "\n"
            "**Reframing**: Show the contradiction rests on a false dichotomy.\n"
            "Name the shared error from Phase 3 and redefine the terms so the\n"
            "opposition dissolves. What question should they have been asking instead?\n"
            "\n"
            "## Phase 5: Save and Report\n"
            "\n"
            "For each synthesis, save it:\n"
            '  mcp__ontology-server__create_idea with author "AI",\n'
            '  tags ["epi-ralph", "contradiction", "<resolution-type-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            "Format:\n"
            "\n"
            "# Generated Ideas — Contradiction Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            f"**Frameworks**: {', '.join(_FRAMEWORKS)}\n"
            "\n"
            "## Thesis\n"
            "**Core Claim**: {the single proposition}\n"
            "**Source**: idea {id}\n"
            "\n"
            "## Antithesis\n"
            "**Core Claim**: {the contradicting proposition}\n"
            "**Source**: idea {id} / constructed\n"
            "**Contradiction Test**: {why these genuinely cannot both be true}\n"
            "\n"
            "## Tension Analysis\n"
            "**Thesis Gets Right**: ...\n"
            "**Antithesis Gets Right**: ...\n"
            "**Shared Error**: ...\n"
            "**Stakes**: ...\n"
            "\n"
            "## Synthesis 1: {Title}\n"
            "**Resolution Type**: Transcendence\n"
            "**The Larger Whole**: {what both positions are partial truths of}\n"
            "**From Thesis**: {what is preserved}\n"
            "**From Antithesis**: {what is preserved}\n"
            "**Novel Contribution**: {what emerges that neither had}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Synthesis 2: {Title}\n"
            "**Resolution Type**: Integration\n"
            "**Kernel from Thesis**: {the valid core}\n"
            "**Kernel from Antithesis**: {the valid core}\n"
            "**New Capability**: {what the framework can do that neither could}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Synthesis 3: {Title}\n"
            "**Resolution Type**: Reframing\n"
            "**False Dichotomy**: {the shared error that creates the opposition}\n"
            "**Better Question**: {what they should have been asking}\n"
            "**Description**: {2-3 sentences}\n"
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return [
            {"name": "mcp__ontology-server__get_idea"},
            {"name": "mcp__ontology-server__query_ideas"},
            {"name": "mcp__ontology-server__create_idea"},
            {"name": "Write"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> EpistemologyOutput:
        return parse_epistemology_output(
            self.phase_id, "contradiction", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
