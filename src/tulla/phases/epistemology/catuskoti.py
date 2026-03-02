"""Epistemology Catuṣkoṭi mode — Nāgārjuna's four-cornered logic.

The catuṣkoṭi mode's distinctive process is a *lattice*: for every claim,
systematically evaluate four truth-value positions — true, false, both true
and false, and neither true nor false.  Ideas emerge from the non-binary
positions (both/neither), which surface paradoxes, category errors, and
genuinely novel framings invisible to binary logic.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = [
    "Tetralemma Navigation",
    "Paradox Exploitation",
    "Category-Error Reframing",
]
_OUTPUT_FILE = "ep-catuskoti-ideas.md"


class CatuskotiPhase(Phase[EpistemologyOutput]):
    """Epistemology catuskoti mode: four-cornered logic surfacing non-binary insight."""

    phase_id: str = "ep-catuskoti"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Catuṣkoṭi Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your reasoning is grounded in the tradition of Nagarjuna and\n"
            "four-cornered logic (catuskoti): systematically examine four\n"
            "truth-value positions — true, false, both true and false, and\n"
            "neither true nor false. Where binary logic forces every proposition\n"
            "into true or false, the catuskoti opens two further positions that\n"
            "reveal paradoxes (both) and category errors (neither). Ideas emerge\n"
            "from these non-binary positions — they are not edge cases but the\n"
            "primary site of insight.\n"
            "\n"
            "## Operational Rules\n"
            "\n"
            "You must obey these 7 constraints throughout:\n"
            "\n"
            "1. EXTRACT 3-5 CORE CLAIMS from the idea and its pool context.\n"
            "   Each claim must be a single declarative sentence that can\n"
            "   meaningfully be evaluated across all four truth-value positions.\n"
            "2. EVALUATE ALL FOUR POSITIONS for every claim. For each claim,\n"
            "   produce a substantive assessment for: (a) true — under what\n"
            "   conditions and framing is this claim straightforwardly true?\n"
            "   (b) false — under what conditions is it straightforwardly false?\n"
            "   (c) both true and false — is there a framing in which the claim\n"
            "   is simultaneously true AND false (a genuine paradox, not mere\n"
            "   ambiguity)? (d) neither true nor false — is there a framing in\n"
            "   which the truth-value question itself is malformed, a category\n"
            "   error, or does not apply?\n"
            "3. DO NOT COLLAPSE TO BINARY. The default for most reasoning is to\n"
            "   treat 'both' as ambiguity and 'neither' as irrelevant. You must\n"
            "   resist this. The non-binary positions are where new ideas live.\n"
            "4. IDENTIFY PARADOXES ('both' positions) explicitly. A paradox is\n"
            "   not just a contradiction — it is a claim that is genuinely true\n"
            "   AND false under defensible framings simultaneously. Map each\n"
            "   paradox: what framing makes it true? What framing makes it false?\n"
            "   Why do both framings have legitimate standing?\n"
            "5. IDENTIFY CATEGORY ERRORS ('neither' positions) explicitly. A\n"
            "   category error means the claim's truth-value question is\n"
            "   malformed — like asking whether the number 7 is heavy. Map each:\n"
            "   what assumption must hold for the claim to be truth-evaluable?\n"
            "   Why might that assumption fail?\n"
            "6. BINARY-FALLBACK GUARD: For empirically resolvable claims (e.g.\n"
            "   'the server responds in < 200ms'), the 'both' and 'neither'\n"
            "   columns may legitimately be N/A. Do NOT force non-binary\n"
            "   positions on claims that are purely empirical. Mark them as\n"
            "   '[empirical — binary sufficient]' and move on.\n"
            "7. GENERATE IDEAS FROM NON-BINARY POSITIONS. Every generated idea\n"
            "   must trace back to a specific 'both' or 'neither' finding.\n"
            "   Ideas from the 'true' or 'false' columns alone are not\n"
            "   catuskoti reasoning — they are ordinary analysis.\n"
            "\n"
            "## Phase 1: Claim Extraction\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            "2. Query the pool for context: mcp__ontology-server__query_ideas\n"
            "3. Extract 3-5 core claims from the idea and its pool context.\n"
            "   Each claim must be a single declarative sentence. Prefer\n"
            "   claims that carry implicit assumptions — these are richest\n"
            "   for four-cornered analysis.\n"
            "\n"
            "## Phase 2: Four-Corner Analysis\n"
            "\n"
            "4. For each extracted claim, evaluate all four truth-value\n"
            "   positions. Write substantive assessments (2-3 sentences each),\n"
            "   not single words. For the 'both' and 'neither' positions,\n"
            "   explicitly name the framing or assumption that opens the\n"
            "   non-binary reading.\n"
            "5. Produce the Claims Table (see output format below).\n"
            "\n"
            "## Phase 3: Non-Binary Insight\n"
            "\n"
            "6. For every claim with a substantive 'both' position, write a\n"
            "   Paradox Map entry: name the paradox, state the two conflicting\n"
            "   framings, and explain why both have standing.\n"
            "7. For every claim with a substantive 'neither' position, write a\n"
            "   Category Error Map entry: name the category error, state the\n"
            "   failed assumption, and explain what question SHOULD be asked\n"
            "   instead.\n"
            "\n"
            "## Phase 4: Idea Generation from Paradox/Category Error\n"
            "\n"
            "8. Generate exactly 3 ideas. Each must trace to a specific\n"
            "   non-binary finding:\n"
            "\n"
            "   **Tetralemma Navigation**: An idea that holds a paradox open\n"
            "   rather than resolving it — what becomes possible if both\n"
            "   framings are simultaneously true?\n"
            "\n"
            "   **Paradox Exploitation**: An idea that USES a 'both' finding\n"
            "   as a design principle — build something that is intentionally\n"
            "   paradoxical (e.g. a feature that is both X and not-X for\n"
            "   different users or at different times).\n"
            "\n"
            "   **Category-Error Reframing**: An idea that emerges from a\n"
            "   'neither' finding — if the original question was malformed,\n"
            "   what is the RIGHT question, and what does it suggest building?\n"
            "\n"
            "9. For each generated idea, save it:\n"
            '   mcp__ontology-server__create_idea with author "AI",\n'
            '   tags ["epi-ralph", "catuskoti", "<protocol-name-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            "Format:\n"
            "\n"
            "# Generated Ideas — Catuṣkoṭi Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            f"**Frameworks**: {', '.join(_FRAMEWORKS)}\n"
            "\n"
            "## Extracted Claims\n"
            "C1: {claim}\n"
            "C2: {claim}\n"
            "C3: {claim}\n"
            "{C4, C5 if extracted}\n"
            "\n"
            "## Claims Table\n"
            "| # | Claim | True | False | Both True and False | Neither True nor False |\n"
            "|---|-------|------|-------|---------------------|------------------------|\n"
            "| C1 | {claim} | {assessment} | {assessment} "
            "| {assessment or [empirical — binary sufficient]} "
            "| {assessment or [empirical — binary sufficient]} |\n"
            "| C2 | ... | ... | ... | ... | ... |\n"
            "| C3 | ... | ... | ... | ... | ... |\n"
            "\n"
            "## Paradox Map\n"
            "**P1: {Paradox Name}** (from C{n})\n"
            "- True-framing: {why the claim is true under this reading}\n"
            "- False-framing: {why the claim is false under this reading}\n"
            "- Standing: {why both framings are legitimate}\n"
            "{repeat for each 'both' finding}\n"
            "\n"
            "## Category Error Map\n"
            "**E1: {Error Name}** (from C{n})\n"
            "- Failed assumption: {what must hold for the claim to be truth-evaluable}\n"
            "- Why it fails: {why that assumption does not hold}\n"
            "- Better question: {the question that should be asked instead}\n"
            "{repeat for each 'neither' finding}\n"
            "\n"
            "## Idea 1: {Title}\n"
            "**Protocol**: Tetralemma Navigation\n"
            "**Source Paradox**: P{n} from C{n}\n"
            "**Non-Binary Insight**: {what the paradox reveals}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Idea 2: {Title}\n"
            "**Protocol**: Paradox Exploitation\n"
            "**Source Paradox**: P{n} from C{n}\n"
            "**Design Principle**: {how the paradox becomes a feature}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Idea 3: {Title}\n"
            "**Protocol**: Category-Error Reframing\n"
            "**Source Error**: E{n} from C{n}\n"
            "**Reframed Question**: {the better question}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Anti-Collapse Guards\n"
            "\n"
            "You MUST populate both the 'Both True and False' and 'Neither True\n"
            "nor False' columns for at least 2 claims. If you find yourself\n"
            "writing N/A for all non-binary columns, you have collapsed to\n"
            "binary — go back and look for hidden assumptions.\n"
            "\n"
            "Do NOT force non-binary positions on empirically resolvable claims.\n"
            "If a claim is purely factual (measurable, observable, decidable),\n"
            "mark the non-binary columns as '[empirical — binary sufficient]'\n"
            "and move on. The catuskoti is for claims with conceptual depth,\n"
            "not for brute facts.\n"
            "\n"
            "Non-binary positions MUST be substantive. 'Both true and false'\n"
            "does not mean 'it depends' — it means there exist two specific,\n"
            "defensible framings under which the claim takes opposite truth\n"
            "values. 'Neither true nor false' does not mean 'I'm not sure' —\n"
            "it means the truth-value question itself is malformed. If you\n"
            "cannot articulate the specific framing or failed assumption,\n"
            "the position is not substantive — leave it as N/A.\n"
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
            self.phase_id, "catuskoti", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
