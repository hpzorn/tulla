"""Epistemology Problem mode — problem archaeology and multi-angle solving.

The problem mode's distinctive process is *diagnostic*: it refuses to
generate solutions until the problem itself is properly understood.  Most
ideas contain problems that are symptoms of deeper issues, or problems
framed so narrowly that good solutions are invisible.  The archaeology
(root-cause analysis, constraint mapping, prior art review) must come
first — premature solution-generation is the enemy.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = [
    "Direct Approach",
    "Analogical Transfer",
    "Assumption Inversion",
    "Decomposition",
]
_OUTPUT_FILE = "ep-problem-ideas.md"


class ProblemPhase(Phase[EpistemologyOutput]):
    """Epistemology problem mode: excavate the real problem, then solve it."""

    phase_id: str = "ep-problem"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Problem Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your job is to find the REAL problem before solving it. You are an\n"
            "archaeologist, not a firefighter. Do not generate solutions until\n"
            "you have excavated the problem structure.\n"
            "\n"
            "## Phase 1: Extract the Stated Problem\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            "2. State the problem the idea is trying to solve, in the idea's own\n"
            "   terms. Quote or paraphrase directly — do not reinterpret yet.\n"
            "\n"
            "## Phase 2: Problem Archaeology\n"
            "\n"
            "3. Apply the Five Whys: ask 'why is this a problem?' repeatedly until\n"
            "   you reach a root cause or a foundational constraint. Write out each\n"
            "   level:\n"
            "   - Why 1: {stated problem} → because {reason}\n"
            "   - Why 2: {reason} → because {deeper reason}\n"
            "   - ... until you hit bedrock\n"
            "\n"
            "4. Map the constraints: what does the idea assume CANNOT be changed?\n"
            "   For each constraint, classify it:\n"
            "   - [hard] — genuinely immovable (physics, law, math)\n"
            "   - [soft] — convention or habit disguised as necessity\n"
            "   - [unknown] — might be movable, not enough information\n"
            "\n"
            "5. Search for prior art:\n"
            "   - Query pool: mcp__ontology-server__query_ideas for related problems\n"
            "   - Use WebSearch for how others have tackled similar problems\n"
            "   Build a prior art inventory: who tried what, and what happened?\n"
            "\n"
            "## Phase 3: Reframe\n"
            "\n"
            "6. Based on the archaeology, state the REAL problem — which may be\n"
            "   different from the stated one. Explain the difference.\n"
            "   If the stated problem IS the real problem, say so and explain why\n"
            "   the archaeology confirmed it.\n"
            "\n"
            "## Phase 4: Generate Solutions\n"
            "\n"
            "Generate exactly 3 solution ideas for the REAL problem (not the\n"
            "stated one, unless they're the same). Choose 3 from:\n"
            "\n"
            "**Direct Approach**: Given the real problem and known constraints,\n"
            "what is the most straightforward solution? This must acknowledge\n"
            "the [hard] constraints and work within them.\n"
            "\n"
            "**Analogical Transfer**: From the prior art search — who solved a\n"
            "structurally similar problem in a different domain? Name them.\n"
            "Map their solution onto this problem specifically.\n"
            "\n"
            "**Assumption Inversion**: Pick a [soft] constraint from the map.\n"
            "What solution becomes possible if you remove it? Is the constraint\n"
            "actually necessary, or just assumed?\n"
            "\n"
            "**Decomposition**: From the Five Whys — is there a sub-problem at\n"
            "an intermediate level that is independently solvable and would\n"
            "unlock progress on the whole? Name the specific level.\n"
            "\n"
            "## Phase 5: Save and Report\n"
            "\n"
            "For each generated idea, save it:\n"
            '  mcp__ontology-server__create_idea with author "AI",\n'
            '  tags ["epi-ralph", "problem", "<protocol-name-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            "Format:\n"
            "\n"
            "# Generated Ideas — Problem Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            "**Frameworks**: {comma-separated list of chosen protocols}\n"
            "\n"
            "## Stated Problem\n"
            "{the problem in the idea's own terms}\n"
            "\n"
            "## Five Whys\n"
            "- Why 1: ...\n"
            "- Why 2: ...\n"
            "- ...\n"
            "**Root Cause**: {where the chain bottoms out}\n"
            "\n"
            "## Constraint Map\n"
            "| Constraint | Type | Notes |\n"
            "|-----------|------|-------|\n"
            "\n"
            "## Prior Art\n"
            "| Who/What | Approach | Outcome |\n"
            "|----------|----------|---------|\n"
            "\n"
            "## Real Problem\n"
            "{reframed problem statement, or confirmation of the original}\n"
            "\n"
            "## Idea 1: {Title}\n"
            "**Protocol**: {name}\n"
            "**Driven By**: {which archaeology finding}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Idea 2: ...\n"
            "## Idea 3: ...\n"
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return [
            {"name": "mcp__ontology-server__get_idea"},
            {"name": "mcp__ontology-server__query_ideas"},
            {"name": "mcp__ontology-server__create_idea"},
            {"name": "WebSearch"},
            {"name": "Write"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> EpistemologyOutput:
        return parse_epistemology_output(
            self.phase_id, "problem", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
