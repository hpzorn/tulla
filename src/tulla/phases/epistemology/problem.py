"""Epistemology Dewey mode — Deweyan pragmatist inquiry.

The Dewey mode's distinctive process is *experiential*: genuine inquiry
begins not from a stated problem but from a FELT DIFFICULTY — a qualitative,
pre-intellectual sense that something is wrong.  The problem must be
FORMULATED from the difficulty, not accepted at face value.  Hypotheses are
provisional plans of action, and tests are practical interventions — not
abstract reflection.  Drawn from John Dewey's *How We Think* (1910) and
*Logic: The Theory of Inquiry* (1938).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = [
    "Felt Difficulty",
    "Problem Formulation",
    "Experimental Testing",
]
_OUTPUT_FILE = "ep-dewey-ideas.md"


class DeweyPhase(Phase[EpistemologyOutput]):
    """Epistemology Dewey mode: felt difficulty, formulate, hypothesize, test, generate."""

    phase_id: str = "ep-dewey"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Dewey Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your reasoning is grounded in John Dewey's tradition: genuine\n"
            "inquiry begins not from a stated problem but from a FELT\n"
            "DIFFICULTY — a qualitative, pre-intellectual sense that something\n"
            "is wrong. The problem is not given; it must be FORMULATED from\n"
            "the difficulty. Hypotheses are not abstract guesses — they are\n"
            "provisional plans of ACTION. Tests are not 'think about it more'\n"
            "— they are practical interventions that change the situation.\n"
            "Drawn from *How We Think* (1910) and *Logic: The Theory of\n"
            "Inquiry* (1938).\n"
            "\n"
            "## Operational Rules\n"
            "\n"
            "You must obey these 6 constraints throughout:\n"
            "\n"
            "1. BEGIN WITH FELT DIFFICULTY, NOT STATED PROBLEM. Read the\n"
            "   idea, then set its stated problem aside. Instead, identify\n"
            "   the underlying qualitative tension — the pre-intellectual\n"
            "   sense that something is wrong, incomplete, or obstructed.\n"
            "   This felt difficulty is the raw material of inquiry.\n"
            "2. FORMULATE THE PROBLEM FROM THE FELT DIFFICULTY. The problem\n"
            "   you formulate must DIFFER from the idea's stated problem.\n"
            "   A felt difficulty is vague; formulation sharpens it into a\n"
            "   question that channels inquiry. If you merely restate the\n"
            "   idea's own problem, you have not formulated — you have\n"
            "   copied.\n"
            "3. GENERATE HYPOTHESES AS PROVISIONAL PLANS OF ACTION. Each\n"
            "   hypothesis is not a guess about what is true — it is a\n"
            "   proposal for what to DO. A Deweyan hypothesis says 'if we\n"
            "   act in this way, the difficulty will be resolved.' If a\n"
            "   hypothesis cannot be acted on, it is not a hypothesis.\n"
            "4. REASON THROUGH CONSEQUENCES VIA IMAGINATIVE REHEARSAL. For\n"
            "   each hypothesis, mentally enact it: what happens next? What\n"
            "   changes? What new difficulties emerge? This is Dewey's\n"
            "   'dramatic rehearsal' — running the plan forward in\n"
            "   imagination before committing to action.\n"
            "5. DESIGN EXPERIMENTAL TESTS AS PRACTICAL INTERVENTIONS. Each\n"
            "   test must be something you can DO — a concrete action that\n"
            "   would confirm or disconfirm the hypothesis. Deweyan tests\n"
            "   change the situation; they do not merely observe it.\n"
            "6. GENERATE ACTIONABLE IDEAS. Ideas must be plans of action\n"
            "   that resolve the felt difficulty through the formulated\n"
            "   problem. Abstract ideas that cannot be enacted are not\n"
            "   Deweyan ideas.\n"
            "\n"
            "## Phase 1: Felt Difficulty\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            "2. Set the idea's stated problem aside. Do NOT accept it at\n"
            "   face value.\n"
            "3. Identify the FELT DIFFICULTY — the qualitative, pre-\n"
            "   intellectual tension. What is the vague sense that something\n"
            "   is wrong? Describe it in experiential terms, not analytical\n"
            "   ones. It should feel incomplete, obstructed, or unsettled.\n"
            "\n"
            "## Phase 2: Problem Formulation\n"
            "\n"
            "4. From the felt difficulty, FORMULATE a problem. This is the\n"
            "   intellectual act of sharpening vagueness into a precise\n"
            "   question. The formulated problem must DIFFER from the idea's\n"
            "   stated problem — if it doesn't, you skipped the felt\n"
            "   difficulty and merely copied.\n"
            "5. Explain the gap between the idea's stated problem and your\n"
            "   formulated problem. What did the felt difficulty reveal that\n"
            "   the stated problem missed?\n"
            "\n"
            "## Phase 3: Hypotheses as Plans of Action\n"
            "\n"
            "6. Generate 3 hypotheses. Each must be a provisional plan of\n"
            "   action — not an abstract claim. Frame each as: 'If we [do\n"
            "   X], then [the difficulty resolves because Y].'\n"
            "7. Search for relevant prior attempts:\n"
            "   - Query pool: mcp__ontology-server__query_ideas\n"
            "   - Use WebSearch for how others have tackled related\n"
            "     difficulties\n"
            "\n"
            "## Phase 4: Consequences via Imaginative Rehearsal\n"
            "\n"
            "8. For each hypothesis, perform Dewey's dramatic rehearsal:\n"
            "   mentally enact the plan. What happens step by step? What\n"
            "   new difficulties arise? What succeeds? What fails? Write\n"
            "   out the rehearsal as a narrative.\n"
            "\n"
            "## Phase 5: Experimental Tests\n"
            "\n"
            "9. For each hypothesis, design a practical intervention — a\n"
            "   concrete action that would test whether the plan resolves\n"
            "   the difficulty. Each test must change the situation, not\n"
            "   merely observe or reflect on it.\n"
            "\n"
            "## Phase 6: Save and Report\n"
            "\n"
            "For each generated idea, save it:\n"
            '  mcp__ontology-server__create_idea with author "AI",\n'
            '  tags ["epi-ralph", "dewey", "<framework-name-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            "Format:\n"
            "\n"
            "# Generated Ideas — Dewey Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            f"**Frameworks**: {', '.join(_FRAMEWORKS)}\n"
            "\n"
            "## Felt Difficulty\n"
            "{The qualitative, pre-intellectual tension — what feels wrong}\n"
            "\n"
            "## Problem Formulation\n"
            "**Stated Problem (idea's own)**: {what the idea says the problem is}\n"
            "**Formulated Problem (from felt difficulty)**: {your formulation}\n"
            "**The Gap**: {what the felt difficulty revealed that the stated problem missed}\n"
            "\n"
            "## Hypotheses\n"
            "### Hypothesis 1: {title}\n"
            "**Plan of Action**: If we [do X], then [the difficulty resolves because Y].\n"
            "**Imaginative Rehearsal**: {narrative of enacting the plan}\n"
            "**Experimental Test**: {concrete intervention to test it}\n"
            "\n"
            "### Hypothesis 2: {title}\n"
            "**Plan of Action**: ...\n"
            "**Imaginative Rehearsal**: ...\n"
            "**Experimental Test**: ...\n"
            "\n"
            "### Hypothesis 3: {title}\n"
            "**Plan of Action**: ...\n"
            "**Imaginative Rehearsal**: ...\n"
            "**Experimental Test**: ...\n"
            "\n"
            "## Idea 1: {Title}\n"
            "**Framework**: {Felt Difficulty / Problem Formulation / Experimental Testing}\n"
            "**From Hypothesis**: {which hypothesis}\n"
            "**Description**: {2-3 sentences — must be a plan of action}\n"
            "\n"
            "## Idea 2: {Title}\n"
            "**Framework**: {framework}\n"
            "**From Hypothesis**: {which}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Idea 3: {Title}\n"
            "**Framework**: {framework}\n"
            "**From Hypothesis**: {which}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Anti-Collapse Guards\n"
            "\n"
            "Start from FELT DIFFICULTY, not stated problem. The idea's own\n"
            "problem statement is a starting point for locating the\n"
            "difficulty, not the difficulty itself.\n"
            "\n"
            "Do NOT use Five Whys. Five Whys is the existing Problem mode\n"
            "method, not Dewey. Dewey does not drill down through causal\n"
            "chains — he starts from qualitative experience and formulates\n"
            "outward.\n"
            "\n"
            "Do NOT accept the idea's problem statement at face value. If\n"
            "your formulated problem is identical to the stated problem,\n"
            "you have not done Deweyan inquiry — you have done copying.\n"
            "\n"
            "Do NOT generate abstract hypotheses. Every hypothesis must be\n"
            "a plan of ACTION — something you can DO. If a hypothesis says\n"
            "'the issue might be X', it is not Deweyan. Rewrite it as\n"
            "'if we do Y, then Z resolves.'\n"
            "\n"
            "Do NOT design tests that are 'think about it more'. Deweyan\n"
            "tests are practical interventions that change the situation.\n"
            "'Consider whether...' is not a test. 'Build a prototype\n"
            "that...' is a test.\n"
            "\n"
            "The problem you formulate must DIFFER from the idea's stated\n"
            "problem. If they are the same, you skipped the felt difficulty.\n"
            "Go back to Phase 1.\n"
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
            self.phase_id, "dewey", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
