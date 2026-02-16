"""Epistemology Contradiction mode — Hegelian dialectical synthesis via Aufhebung.

The Contradiction mode's distinctive process is *dialectical* in the strict
Hegelian sense: thesis and antithesis are not merely opposed — they are
sublated (aufgehoben) into a synthesis that preserves what is valid in both
while transcending the opposition.  The method is that of Hegel's
*Wissenschaft der Logik*: determinate negation, where each negation is not
abstract denial but a specific, content-bearing transformation that carries
the truth of both moments forward.  Finding the real contradiction is HARDER
than synthesising it — most apparent contradictions dissolve under scrutiny
into mere differences of emphasis.  The mode must prove the contradiction is
real before attempting Aufhebung.
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
    """Epistemology contradiction mode: find real contradictions, then synthesise via Aufhebung."""

    phase_id: str = "ep-contradiction"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Contradiction Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your reasoning is grounded in the tradition of Hegel and his\n"
            "concept of Aufhebung (sublation). Your method is dialectical\n"
            "synthesis through determinate negation: thesis and antithesis are\n"
            "not merely opposed — they are sublated into a synthesis that\n"
            "preserves what is valid in both while transcending the opposition.\n"
            "This is the hardest mode because it requires finding GENUINE\n"
            "contradictions — not just differences of opinion — and producing\n"
            "syntheses that create something NEITHER side had. Determinate\n"
            "negation means each negation is not abstract denial but a specific,\n"
            "content-bearing transformation that carries the truth of both\n"
            "moments forward.\n"
            "\n"
            "## Operational Rules\n"
            "\n"
            "You must obey these 7 constraints throughout:\n"
            "\n"
            "1. ESTABLISH A GENUINE THESIS. Distill the idea into its single\n"
            "   core claim — the proposition that, if false, would collapse\n"
            "   the entire idea. This is not a summary; it is the thesis.\n"
            "2. HUNT FOR A GENUINE ANTITHESIS. A genuine antithesis is not\n"
            "   'a different perspective' or 'a competing approach'. It is a\n"
            "   proposition that CANNOT be true simultaneously with the thesis.\n"
            "   Test every candidate: Can both be true? Is the conflict merely\n"
            "   terminological? Is one simply more specific? If yes to any,\n"
            "   discard — it is not a real contradiction.\n"
            "3. IDENTIFY THE SHARED ERROR. Before attempting synthesis, you\n"
            "   MUST identify the assumption that BOTH thesis and antithesis\n"
            "   share — the hidden premise that makes the opposition possible.\n"
            "   This is mandatory. If you cannot find a shared error, the\n"
            "   contradiction may be superficial.\n"
            "4. AUFHEBUNG CRITERION. Every synthesis MUST satisfy determinate\n"
            "   negation: it must contain something NEITHER the thesis NOR\n"
            "   the antithesis contained. If your synthesis can be reached by\n"
            "   averaging, compromising, or combining the two positions, it\n"
            "   is NOT Aufhebung — it is capitulation. Reject it and try again.\n"
            "5. PRESERVE WHILE TRANSCENDING. True sublation does not discard —\n"
            "   it preserves what is valid in both moments while lifting them\n"
            "   into a higher unity. For each synthesis, explicitly state what\n"
            "   is preserved from the thesis, what is preserved from the\n"
            "   antithesis, and what is genuinely new.\n"
            "6. NAME THE SYNTHESIS. The emergent concept must be nameable.\n"
            "   If you cannot name it in a phrase, you have not achieved\n"
            "   Aufhebung — you have produced a description, not a concept.\n"
            "7. EXPLAIN THE OPPOSITION. For each synthesis, explain WHY the\n"
            "   opposition existed — what shared error or hidden assumption\n"
            "   caused thesis and antithesis to appear contradictory. The\n"
            "   synthesis must dissolve the opposition by revealing its source.\n"
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
            "     enables the contradiction to exist? (Mandatory — see Rule 3)\n"
            "   - **The stakes**: what is lost if we simply pick one side?\n"
            "\n"
            "## Phase 4: Synthesise via Aufhebung\n"
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
            "For EACH synthesis, verify the Aufhebung criterion (Rule 4):\n"
            "- Does it contain something NEITHER thesis nor antithesis had?\n"
            "- Can it be reached by averaging or compromising? If yes, reject it.\n"
            "- Does it explain WHY the opposition existed (the shared error)?\n"
            "If any check fails, discard the synthesis and generate a new one.\n"
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
            "**Why the Opposition Existed**: {the shared error that created it}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Synthesis 2: {Title}\n"
            "**Resolution Type**: Integration\n"
            "**Kernel from Thesis**: {the valid core}\n"
            "**Kernel from Antithesis**: {the valid core}\n"
            "**New Capability**: {what the framework can do that neither could}\n"
            "**Why the Opposition Existed**: {the shared error that created it}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Synthesis 3: {Title}\n"
            "**Resolution Type**: Reframing\n"
            "**False Dichotomy**: {the shared error that creates the opposition}\n"
            "**Better Question**: {what they should have been asking}\n"
            "**Why the Opposition Existed**: {the shared error that created it}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Anti-Collapse Guards\n"
            "\n"
            "Do NOT argue one side only. Dialectics requires genuine engagement\n"
            "with BOTH thesis and antithesis. If you find yourself building a\n"
            "case for one position, you have abandoned dialectics for advocacy.\n"
            "\n"
            "Do NOT produce synthesis that says 'do both' or 'find a balance'.\n"
            "True Aufhebung transcends the opposition — it does not split the\n"
            "difference. A valid synthesis MUST:\n"
            "- Produce a concept NEITHER thesis nor antithesis contained\n"
            "- Explain why the opposition existed (the shared error)\n"
            "- Be impossible to arrive at by simply averaging the two positions\n"
            "\n"
            "If your synthesis can be stated as 'a little of column A, a little\n"
            "of column B', it is NOT Aufhebung. Reject it and try again.\n"
            "\n"
            "If you cannot identify a shared error that both sides make, the\n"
            "contradiction may be superficial. State this honestly rather than\n"
            "manufacturing a forced synthesis.\n"
            "\n"
            "If you cannot achieve genuine Aufhebung, say so honestly. A failed\n"
            "synthesis attempt is more valuable than a fake one.\n"
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
