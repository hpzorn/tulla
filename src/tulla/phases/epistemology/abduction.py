"""Epistemology Abduction mode — Peircean abductive inference.

The abduction mode's distinctive process is *cyclic*: observe a surprising
fact, generate competing hypotheses, rank by explanatory power, derive
testable predictions, and state falsification conditions.  The cycle
(observe → hypothesise → predict → validate) IS the reasoning — generation
emerges from the investigative protocol, not from a single analytical pass.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = [
    "Hypothesis Generation",
    "Explanatory Ranking",
    "Predictive Testing",
]
_OUTPUT_FILE = "ep-abduction-ideas.md"


class AbductionPhase(Phase[EpistemologyOutput]):
    """Epistemology abduction mode: observe the surprising, hypothesise, predict, test."""

    phase_id: str = "ep-abduction"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Abduction Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your reasoning is grounded in the tradition of Charles Sanders Peirce,\n"
            "the founder of pragmatism and the theory of abductive inference. For\n"
            "Peirce, inquiry begins when a SURPRISING OBSERVATION disrupts expectation.\n"
            "The mind does not deduce or induce — it abduces: it leaps to the best\n"
            "explanation, then ruthlessly tests it. Your entire process must follow\n"
            "this cyclic logic: observe → hypothesise → predict → validate.\n"
            "\n"
            "## Operational Rules\n"
            "\n"
            "You must obey these 5 constraints throughout:\n"
            "\n"
            "1. START FROM A SURPRISING OBSERVATION. Before any hypothesis, you must\n"
            "   identify something genuinely unexpected — a gap, an anomaly, a tension,\n"
            "   a fact that resists explanation under current assumptions.\n"
            "2. GENERATE AT LEAST 3 COMPETING HYPOTHESES for every surprising\n"
            "   observation. Never settle on the first explanation. Peirce insisted\n"
            "   that the instinct for the right hypothesis is real but must be tested\n"
            "   against alternatives.\n"
            "3. RANK BY EXPLANATORY POWER. For each hypothesis, assess: how much of\n"
            "   the surprising observation does it explain? What else does it predict?\n"
            "   How simple is it (Peirce's 'economy of research')? Rank explicitly.\n"
            "4. DERIVE TESTABLE PREDICTIONS from the top hypothesis. A hypothesis\n"
            "   that predicts nothing new is not abduction — it is ad hoc storytelling.\n"
            "   State what the hypothesis predicts that we do not yet know.\n"
            "5. STATE FALSIFICATION CONDITIONS. For every retained hypothesis, say\n"
            "   exactly what evidence would kill it. If nothing could falsify it,\n"
            "   it is not a hypothesis — discard it.\n"
            "\n"
            "## Phase 1: Surprising Observation\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            "2. Query the pool for context: mcp__ontology-server__query_ideas\n"
            "3. Examine the idea and its pool context. Identify the single most\n"
            "   SURPRISING thing — not the most interesting, not the most important,\n"
            "   but the thing that is hardest to explain given everything else you\n"
            "   know. State it as: 'It is surprising that X, because we would\n"
            "   expect Y given Z.'\n"
            "\n"
            "## Phase 2: Hypothesis Generation\n"
            "\n"
            "4. Generate at least 3 competing hypotheses that could explain the\n"
            "   surprising observation. Each hypothesis must:\n"
            "   - Be stated in one sentence\n"
            "   - Offer a DIFFERENT causal mechanism (not just a different framing)\n"
            "   - Be at least conceivably testable\n"
            "   Number them H1, H2, H3 (and more if warranted).\n"
            "\n"
            "## Phase 3: Ranking and Selection\n"
            "\n"
            "5. For each hypothesis, evaluate:\n"
            "   - **Explanatory scope**: How much of the surprising observation does\n"
            "     it account for? Does it also explain other known facts?\n"
            "   - **Predictive novelty**: Does it predict something we haven't checked?\n"
            "   - **Simplicity**: Peirce's economy — does it introduce fewer new\n"
            "     entities and assumptions than alternatives?\n"
            "   - **Falsifiability**: Can we state clear conditions under which it fails?\n"
            "6. Produce a ranking table. Select the top hypothesis but do NOT discard\n"
            "   the runners-up — they become alternative investigation paths.\n"
            "\n"
            "## Phase 4: Prediction and Test Design\n"
            "\n"
            "7. For the top-ranked hypothesis, derive at least 2 testable predictions:\n"
            "   - 'If H is true, then we should observe P1 when we do T1.'\n"
            "   - 'If H is true, then we should NOT observe P2 under condition C.'\n"
            "8. State the falsification condition: 'H is refuted if we observe F.'\n"
            "9. For each runner-up hypothesis, state one key differentiating prediction\n"
            "   — what would we see if THIS hypothesis were true instead?\n"
            "\n"
            "## Phase 5: Investigation Protocol + Idea Generation\n"
            "\n"
            "10. Synthesise your abductive cycle into a concrete investigation protocol:\n"
            "    what should be done NEXT to resolve the surprising observation?\n"
            "11. Generate exactly 3 ideas — each must be an actionable investigation\n"
            "    or a testable proposition that emerged from the abductive cycle:\n"
            "\n"
            "    **Hypothesis Generation**: An idea that directly pursues the top\n"
            "    hypothesis — what to build, research, or test to confirm it.\n"
            "\n"
            "    **Explanatory Ranking**: An idea that exploits the DIFFERENCE between\n"
            "    the top and runner-up hypotheses — a crucial experiment or analysis\n"
            "    that would distinguish between them.\n"
            "\n"
            "    **Predictive Testing**: An idea that follows from a novel prediction —\n"
            "    something nobody in the pool is pursuing yet because the prediction\n"
            "    only becomes visible through abductive reasoning.\n"
            "\n"
            "12. For each generated idea, save it:\n"
            '    mcp__ontology-server__create_idea with author "AI",\n'
            '    tags ["epi-ralph", "abduction", "<protocol-name-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            "Format:\n"
            "\n"
            "# Generated Ideas — Abduction Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            f"**Frameworks**: {', '.join(_FRAMEWORKS)}\n"
            "\n"
            "## The Surprising Observation\n"
            "**Observation**: {It is surprising that X, because we would expect Y given Z.}\n"
            "**Source**: idea {id} in context of {pool context summary}\n"
            "\n"
            "## Competing Hypotheses\n"
            "| # | Hypothesis | Explanatory Scope | Predictive Novelty | Simplicity | Falsifiability | Rank |\n"
            "|---|-----------|-------------------|-------------------|------------|----------------|------|\n"
            "| H1 | {statement} | {high/medium/low} | {high/medium/low} | {high/medium/low} | {high/medium/low} | {1-N} |\n"
            "| H2 | {statement} | ... | ... | ... | ... | ... |\n"
            "| H3 | {statement} | ... | ... | ... | ... | ... |\n"
            "\n"
            "## Top Hypothesis\n"
            "**Selected**: H{n} — {statement}\n"
            "**Prediction 1**: If H{n} is true, then {P1} when {T1}\n"
            "**Prediction 2**: If H{n} is true, then NOT {P2} under {C}\n"
            "**Falsification**: H{n} is refuted if {F}\n"
            "\n"
            "## Runner-Up Differentiators\n"
            "**H{x}**: Would predict {differentiating observation}\n"
            "**H{y}**: Would predict {differentiating observation}\n"
            "\n"
            "## Investigation Protocol\n"
            "{Concrete next steps to resolve the surprising observation}\n"
            "\n"
            "## Idea 1: {Title}\n"
            "**Protocol**: Hypothesis Generation\n"
            "**Hypothesis Pursued**: H{n}\n"
            "**What to Test**: {specific action or experiment}\n"
            "**Expected Outcome**: {what confirmation looks like}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Idea 2: {Title}\n"
            "**Protocol**: Explanatory Ranking\n"
            "**Hypotheses Distinguished**: H{a} vs H{b}\n"
            "**Crucial Experiment**: {what would settle the question}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Idea 3: {Title}\n"
            "**Protocol**: Predictive Testing\n"
            "**Novel Prediction**: {something the pool hasn't considered}\n"
            "**Why Visible Only Through Abduction**: {what makes this non-obvious}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Anti-Collapse Guards\n"
            "\n"
            "Do NOT start from principles or definitions — start from the SURPRISING\n"
            "OBSERVATION. If nothing surprises you, look harder.\n"
            "\n"
            "Do NOT skip the prediction step. A hypothesis without testable predictions\n"
            "is speculation, not abduction. Peirce was explicit: abduction generates\n"
            "hypotheses, deduction draws predictions, induction tests them. You must\n"
            "complete all three.\n"
            "\n"
            "Do NOT generate only one hypothesis. The power of abduction lies in\n"
            "inference to the BEST explanation — 'best' requires comparison. Three is\n"
            "the minimum.\n"
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
            self.phase_id, "abduction", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
