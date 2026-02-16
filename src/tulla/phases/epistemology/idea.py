"""Epistemology Aristotle mode — Aristotelian Four Causes analysis.

The Aristotle mode's distinctive process is *causal*: it investigates a
single idea through four independent causal questions — material, formal,
efficient, final — drawn from Aristotle's Physics II and Metaphysics V.
Each cause is explored separately before integration; ideas emerge from
causal gaps and conflicts revealed only when all four inquiries are
complete and juxtaposed.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = [
    "Material Cause",
    "Formal Cause",
    "Efficient Cause",
    "Final Cause",
]
_OUTPUT_FILE = "ep-aristotle-ideas.md"


class AristotlePhase(Phase[EpistemologyOutput]):
    """Epistemology Aristotle mode: four independent causal inquiries, integrate, generate."""

    phase_id: str = "ep-aristotle"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Aristotle Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your reasoning is grounded in Aristotle's tradition: to truly\n"
            "understand anything, you must answer four independent causal\n"
            "questions — material, formal, efficient, final. Your method is\n"
            "drawn from Physics II and Metaphysics V. Understanding is not a\n"
            "single explanation but the convergence of four distinct lines of\n"
            "inquiry, each irreducible to the others.\n"
            "\n"
            "## Operational Rules\n"
            "\n"
            "You must obey these 7 constraints throughout:\n"
            "\n"
            "1. FOUR INDEPENDENT CAUSAL INQUIRIES. Each cause (material,\n"
            "   formal, efficient, final) must be investigated as a separate,\n"
            "   self-contained inquiry. Do not let one cause's answer leak\n"
            "   into another's investigation.\n"
            "2. MATERIAL CAUSE FIRST. Begin with what the idea is made of —\n"
            "   its constituents, ingredients, substrates. What pre-existing\n"
            "   concepts, technologies, or structures compose it?\n"
            "3. FORMAL CAUSE SECOND. What is the idea's defining structure,\n"
            "   pattern, or arrangement? What makes it THIS idea rather than\n"
            "   some other configuration of the same materials?\n"
            "4. EFFICIENT CAUSE THIRD. What brought this idea into being?\n"
            "   What agent, process, or event initiated it? What triggered\n"
            "   its creation?\n"
            "5. FINAL CAUSE FOURTH. What is the idea's telos — its end, goal,\n"
            "   or purpose? What is it FOR? What would it look like fully\n"
            "   realized?\n"
            "6. INTEGRATE AFTER ALL FOUR. Only after completing all four\n"
            "   independent inquiries, juxtapose the answers. Look for gaps\n"
            "   (a cause that has no clear answer), conflicts (causes that\n"
            "   point in different directions), and surprises (a cause that\n"
            "   reveals something the others missed).\n"
            "7. GENERATE FROM CAUSAL GAPS AND CONFLICTS. Ideas emerge from\n"
            "   what the four-cause analysis reveals — missing causes,\n"
            "   contradictory causes, or unexpected alignments. Not from\n"
            "   generic brainstorming.\n"
            "\n"
            "## Phase 1: Material Cause\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            f"2. Get its neighbours: mcp__ontology-server__get_related_ideas for {ctx.idea_id}\n"
            "3. Read each neighbour with mcp__ontology-server__get_idea.\n"
            "\n"
            "Now investigate the Material Cause: What is this idea made of?\n"
            "What pre-existing concepts, technologies, materials, or knowledge\n"
            "compose it? What are its raw ingredients? Enumerate every\n"
            "constituent you can identify.\n"
            "\n"
            "## Phase 2: Formal Cause\n"
            "\n"
            "4. Investigate the Formal Cause independently: What is the\n"
            "   idea's defining structure or pattern? What arrangement of its\n"
            "   materials makes it THIS specific idea? What is its essential\n"
            "   form — the blueprint, schema, or organizing principle?\n"
            "\n"
            "## Phase 3: Efficient Cause\n"
            "\n"
            "5. Investigate the Efficient Cause independently: What brought\n"
            "   this idea into being? What agent, event, need, or process\n"
            "   initiated it? What is the proximate trigger and the deeper\n"
            "   chain of causes behind that trigger?\n"
            "\n"
            "## Phase 4: Final Cause\n"
            "\n"
            "6. Investigate the Final Cause independently: What is this\n"
            "   idea's telos? What is it ultimately FOR? What would full\n"
            "   realization look like? What end state does it aim toward?\n"
            "\n"
            "## Phase 5: Causal Integration\n"
            "\n"
            "7. Now — and only now — juxtapose all four answers. Identify:\n"
            "   - **Causal gaps**: Which cause has the weakest or most\n"
            "     uncertain answer? A gap is a generative opening.\n"
            "   - **Causal conflicts**: Do any causes point in contradictory\n"
            "     directions? (e.g., the formal cause suggests elegance but\n"
            "     the efficient cause was a quick hack)\n"
            "   - **Causal surprises**: Did any single cause reveal something\n"
            "     invisible from the others?\n"
            "\n"
            "## Phase 6: Idea Generation\n"
            "\n"
            "Generate exactly 3 ideas from the causal analysis. Each must\n"
            "emerge from a specific gap, conflict, or surprise identified in\n"
            "the integration phase. For each, tag with the most relevant\n"
            "cause framework:\n"
            "\n"
            "**Material Cause**: An idea that addresses a missing or\n"
            "underexplored constituent — new raw material that would change\n"
            "what the idea is made of.\n"
            "\n"
            "**Formal Cause**: An idea that proposes a different organizing\n"
            "structure — a rearrangement that transforms the same materials\n"
            "into something new.\n"
            "\n"
            "**Efficient Cause**: An idea that addresses a gap in how the\n"
            "idea comes into being — a new trigger, process, or agent.\n"
            "\n"
            "**Final Cause**: An idea that redefines the telos — a different\n"
            "end, purpose, or realization that the current form could serve.\n"
            "\n"
            "## Phase 7: Save and Report\n"
            "\n"
            "For each generated idea, save it:\n"
            '  mcp__ontology-server__create_idea with author "AI",\n'
            '  tags ["epi-ralph", "aristotle", "<cause-name-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            "Format:\n"
            "\n"
            "# Generated Ideas — Aristotle Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            f"**Frameworks**: {', '.join(_FRAMEWORKS)}\n"
            "\n"
            "## Material Cause\n"
            "{What the idea is made of — its constituents and substrates}\n"
            "\n"
            "## Formal Cause\n"
            "{The idea's defining structure, pattern, or organizing principle}\n"
            "\n"
            "## Efficient Cause\n"
            "{What brought the idea into being — trigger, agent, process}\n"
            "\n"
            "## Final Cause\n"
            "{The idea's telos — its end, purpose, and full realization}\n"
            "\n"
            "## Causal Integration\n"
            "**Gaps**: {which cause is weakest}\n"
            "**Conflicts**: {which causes contradict}\n"
            "**Surprises**: {what one cause revealed that others missed}\n"
            "\n"
            "## Idea 1: {Title}\n"
            "**Framework**: {Material Cause / Formal Cause / Efficient Cause / Final Cause}\n"
            "**Causal Origin**: {which gap, conflict, or surprise}\n"
            "**Source Ideas**: {root + any neighbours used}\n"
            "**Description**: {2-3 sentences}\n"
            "**Novelty**: {why distinct from existing ideas}\n"
            "\n"
            "## Idea 2: {Title}\n"
            "**Framework**: {cause}\n"
            "**Causal Origin**: {which gap, conflict, or surprise}\n"
            "**Source Ideas**: {ids}\n"
            "**Description**: {2-3 sentences}\n"
            "**Novelty**: {why distinct}\n"
            "\n"
            "## Idea 3: {Title}\n"
            "**Framework**: {cause}\n"
            "**Causal Origin**: {which gap, conflict, or surprise}\n"
            "**Source Ideas**: {ids}\n"
            "**Description**: {2-3 sentences}\n"
            "**Novelty**: {why distinct}\n"
            "\n"
            "## Anti-Collapse Guards\n"
            "\n"
            "Do NOT skip to efficient cause. Efficient cause (who made it,\n"
            "what triggered it) is the least interesting causal question —\n"
            "it is the default question everyone asks. The other three\n"
            "causes are where genuine insight lives.\n"
            "\n"
            "Each cause MUST be investigated independently BEFORE integration.\n"
            "If you find yourself referencing one cause's answer while\n"
            "investigating another, stop and separate them.\n"
            "\n"
            "If you answer Material Cause by saying 'it was built by X\n"
            "for Y', you have collapsed material into efficient + final.\n"
            "Material cause asks WHAT it is made of, not WHO made it or\n"
            "WHY. Strip the agent and purpose — what remains?\n"
            "\n"
            "Do NOT treat the four causes as a checklist to rush through.\n"
            "Each is a complete inquiry. If a cause gets only one sentence,\n"
            "you have not investigated — you have labeled.\n"
            "\n"
            "Integration comes AFTER all four, never during. If your\n"
            "Formal Cause section references the Final Cause, you are\n"
            "integrating prematurely.\n"
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return [
            {"name": "mcp__ontology-server__get_idea"},
            {"name": "mcp__ontology-server__query_ideas"},
            {"name": "mcp__ontology-server__get_related_ideas"},
            {"name": "mcp__ontology-server__create_idea"},
            {"name": "Write"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> EpistemologyOutput:
        return parse_epistemology_output(
            self.phase_id, "aristotle", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
