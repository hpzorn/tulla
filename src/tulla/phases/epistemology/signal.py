"""Epistemology Pyrrhon mode — Pyrrhonian skeptical suspension.

The Pyrrhon mode's distinctive process is *equipollent*: it constructs
equally compelling cases FOR and AGAINST a central claim, then suspends
judgment (epochē).  Ideas emerge not from resolution but from the clarity
that becomes visible when you stop trying to decide.  The method is that
of Sextus Empiricus — isostheneia (equal weight) is the engine, not a
failure state.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = ["Equipollence", "Epoche", "Suspension"]
_OUTPUT_FILE = "ep-pyrrhon-ideas.md"


class PyrrhonPhase(Phase[EpistemologyOutput]):
    """Epistemology Pyrrhon mode: construct equipollent arguments, suspend, generate from stillness."""

    phase_id: str = "ep-pyrrhon"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Pyrrhon Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your reasoning is grounded in the tradition of Sextus Empiricus and\n"
            "Pyrrhonian Skepticism. Your method is equipollent argumentation:\n"
            "constructing equally compelling cases FOR and AGAINST a central claim,\n"
            "then suspending judgment (epochē). Ideas emerge not from resolution\n"
            "but from the clarity that becomes visible only when you stop trying\n"
            "to decide. Isostheneia — equal weight of opposing arguments — is\n"
            "the engine, not a failure state.\n"
            "\n"
            "## Operational Rules\n"
            "\n"
            "You must obey these 6 constraints throughout:\n"
            "\n"
            "1. STATE THE CENTRAL CLAIM. Before anything else, distill the idea\n"
            "   into a single, decidable proposition — a claim that can be argued\n"
            "   for or against. If the idea is too vague, sharpen it until it is.\n"
            "2. CONSTRUCT THE STRONGEST CASE FOR. Marshal the best evidence,\n"
            "   reasoning, and arguments in favour of the claim. Be a genuine\n"
            "   advocate — this must be compelling on its own.\n"
            "3. CONSTRUCT AN EQUALLY STRONG CASE AGAINST (isostheneia = equal\n"
            "   weight). This is the hard part. The case against must match the\n"
            "   case for in depth, specificity, and persuasive force. If it is\n"
            "   shorter or weaker, rewrite it until they are balanced.\n"
            "4. DEMONSTRATE EQUIPOLLENCE. Show explicitly that neither case\n"
            "   defeats the other — that a rational agent, considering both,\n"
            "   cannot prefer one over the other without importing assumptions\n"
            "   external to the arguments themselves.\n"
            "5. SUSPEND JUDGMENT (epochē). Do not resolve the tension. Instead,\n"
            "   describe what becomes visible when you stop trying to decide.\n"
            "   What questions appear? What hidden assumptions surface? What\n"
            "   adjacent territories reveal themselves?\n"
            "6. GENERATE IDEAS FROM SUSPENSION. The ideas must emerge from what\n"
            "   suspension reveals — not from picking a side, not from\n"
            "   compromise, not from 'it depends'. Each idea must be something\n"
            "   that would be invisible to someone who had already decided.\n"
            "\n"
            "## Phase 1: The Claim\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            "2. Query the pool for context: mcp__ontology-server__query_ideas\n"
            "3. Distill the idea into a single central claim — a proposition\n"
            "   that is specific enough to argue for and against.\n"
            "\n"
            "## Phase 2: Case FOR\n"
            "\n"
            "4. Construct the strongest possible case FOR the claim. Use\n"
            "   evidence, reasoning, precedent, and logical argument. This is\n"
            "   not a strawman — it must be genuinely compelling.\n"
            "\n"
            "## Phase 3: Case AGAINST\n"
            "\n"
            "5. Construct the strongest possible case AGAINST the claim. It must\n"
            "   match the case FOR in length, depth, and persuasive force\n"
            "   (isostheneia). If your initial attempt is weaker than the case\n"
            "   FOR, rewrite until they are balanced.\n"
            "\n"
            "## Phase 4: Equipollence and Epochē\n"
            "\n"
            "6. Demonstrate that neither case defeats the other. Show the\n"
            "   equipollence explicitly.\n"
            "7. Suspend judgment. Describe what becomes visible from the\n"
            "   suspension — new questions, hidden assumptions, adjacent\n"
            "   territories, overlooked dimensions.\n"
            "\n"
            "## Phase 5: Generate from Suspension\n"
            "\n"
            "Generate exactly 3 ideas. Each must emerge from what epochē\n"
            "reveals — from the space that opens when judgment is suspended.\n"
            "For each, choose the most fitting framework:\n"
            "\n"
            "**Equipollence**: An idea that holds both sides in tension\n"
            "productively — a research question, design, or investigation\n"
            "that requires BOTH perspectives to remain open.\n"
            "\n"
            "**Epoche**: An idea that exploits what suspension reveals —\n"
            "something that only becomes visible when you stop trying to\n"
            "decide. A hidden assumption, an overlooked dimension, a question\n"
            "nobody asked because they were busy arguing.\n"
            "\n"
            "**Suspension**: An idea that lives in the undecided space itself —\n"
            "a tool, process, or approach that is valuable precisely because\n"
            "it does not resolve the tension.\n"
            "\n"
            "## Phase 6: Save and Report\n"
            "\n"
            "For each generated idea, save it:\n"
            '  mcp__ontology-server__create_idea with author "AI",\n'
            '  tags ["epi-ralph", "pyrrhon", "<framework-name-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            "Format:\n"
            "\n"
            "# Generated Ideas — Pyrrhon Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            f"**Frameworks**: {', '.join(_FRAMEWORKS)}\n"
            "\n"
            "## The Claim\n"
            "**Central Proposition**: {the single decidable claim}\n"
            "**Source**: idea {id}\n"
            "\n"
            "## Case FOR\n"
            "{Full argument in favour — at least 3 substantive points}\n"
            "\n"
            "## Case AGAINST\n"
            "{Full argument against — matched in length and force to Case FOR}\n"
            "\n"
            "## Equipollence\n"
            "{Demonstration that neither case defeats the other}\n"
            "\n"
            "## What Suspension Reveals\n"
            "{What becomes visible when you stop trying to decide}\n"
            "\n"
            "## Idea 1: {Title}\n"
            "**Framework**: Equipollence\n"
            "**Emerged From**: {what aspect of the suspended judgment}\n"
            "**Why Invisible to the Decided**: {why resolving would hide this}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Idea 2: {Title}\n"
            "**Framework**: Epoche\n"
            "**Hidden Assumption Surfaced**: {what epochē revealed}\n"
            "**Why Invisible to the Decided**: {why resolving would hide this}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Idea 3: {Title}\n"
            "**Framework**: Suspension\n"
            "**Value of Non-Resolution**: {why not deciding is productive here}\n"
            "**Why Invisible to the Decided**: {why resolving would hide this}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Anti-Collapse Guards\n"
            "\n"
            "Do NOT resolve the tension. The entire point of Pyrrhonian\n"
            "skepticism is that epochē (suspension) is the goal, not a waypoint\n"
            "to resolution.\n"
            "\n"
            "Do NOT pick a side. If you find yourself leaning, rebalance the\n"
            "cases until equipollence is restored.\n"
            "\n"
            "Do NOT say 'both sides have valid points' — that IS resolution\n"
            "(a weak form of synthesis). Equipollence means neither side wins,\n"
            "not that both sides win.\n"
            "\n"
            "Do NOT say 'it depends on context' — that is evasion, not\n"
            "suspension. Epochē is actively holding the tension, not deferring\n"
            "the decision to circumstances.\n"
            "\n"
            "If the Case AGAINST is shorter or weaker than the Case FOR,\n"
            "REWRITE it until they match. Isostheneia is non-negotiable.\n"
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
            self.phase_id, "pyrrhon", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
