"""Epistemology Auto mode — topology-grounded meta-epistemological selector.

The auto mode is the *meta-epistemologist* of the system: it diagnoses the
epistemological situation of an idea along 8 philosopher-grounded dimensions,
then prescribes the TOP 3 most applicable reasoning modes based on evidence.
It is the only mode that begins with diagnosis — the mode selection itself is
a reasoned act grounded in the idea's actual epistemic needs, not a mechanical
dispatch or aesthetic preference.

Modes available for selection:
  Pyrrhonian Skepticism, Peircean Abduction, Hegelian Dialectics,
  Catuṣkoṭi (Nāgārjuna), Aristotelian Four Causes, Deweyan Inquiry,
  Popperian Falsification, Baconian Inductivism.

Fallback: Peircean Abduction (when no strong diagnostic match).
Mutual exclusion: Popper and Bacon may not both be selected.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_ALL_FRAMEWORKS = [
    "Pyrrhonian Skepticism",
    "Peircean Abduction",
    "Hegelian Dialectics",
    "Catuṣkoṭi",
    "Aristotelian Four Causes",
    "Deweyan Inquiry",
    "Popperian Falsification",
    "Baconian Inductivism",
]
_OUTPUT_FILE = "ep-auto-ideas.md"


class AutoPhase(Phase[EpistemologyOutput]):
    """Epistemology auto mode: diagnose the idea's epistemological situation, then select and apply philosopher-grounded modes."""

    phase_id: str = "ep-auto"
    timeout_s: float = 1200.0  # 20 minutes — larger scope

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            # ── Layer 1: Persona ──────────────────────────────────────────
            "You are a meta-epistemologist who diagnoses which WAY OF THINKING\n"
            "is most productive for this specific idea based on its\n"
            f"epistemological situation. You are working on idea {ctx.idea_id}.\n"
            "\n"
            # ── Layer 2: Operational Rules ────────────────────────────────
            "## Phase 1: Examine the Idea\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            f"2. Get neighbours: mcp__ontology-server__get_related_ideas for {ctx.idea_id}\n"
            "3. Query broader pool: mcp__ontology-server__query_ideas\n"
            "\n"
            "## Phase 2: Diagnose the Epistemological Situation\n"
            "\n"
            "Assess the idea along these 8 diagnostic questions. For EACH question,\n"
            "cite specific evidence from the idea. If you cannot cite evidence,\n"
            "the diagnosis is WRONG — mark it N/A.\n"
            "\n"
            "1. **Contested Claims → Pyrrhonian Skepticism**: Does the idea contain\n"
            "   claims that are actively contested, dogmatically asserted, or accepted\n"
            "   without sufficient warrant? Evidence: {specific contested claims}\n"
            "2. **Unexplained Anomaly → Peircean Abduction**: Does the idea exhibit\n"
            "   a surprising observation, anomaly, or phenomenon that lacks a\n"
            "   satisfying explanation? Evidence: {the specific anomaly}\n"
            "3. **Genuine Contradiction → Hegelian Dialectics**: Does the idea contain\n"
            "   a genuine contradiction — two forces, requirements, or truths that\n"
            "   are BOTH valid yet incompatible? Evidence: {the thesis and antithesis}\n"
            "4. **Non-Binary Tension → Catuṣkoṭi**: Does the idea involve a tension\n"
            "   that resists binary resolution — where the answer is neither A nor B,\n"
            "   or perhaps both and neither? Evidence: {the non-binary tension}\n"
            "5. **Unclear Purpose/Composition → Aristotelian Four Causes**: Is the\n"
            "   idea's purpose (final cause), mechanism (efficient cause), structure\n"
            "   (formal cause), or material basis unclear or under-specified?\n"
            "   Evidence: {which cause is missing or unclear}\n"
            "6. **Indeterminate Situation → Deweyan Inquiry**: Is the idea in a state\n"
            "   of genuine indeterminacy — a felt difficulty without a clear problem\n"
            "   formulation? Evidence: {the indeterminate situation}\n"
            "7. **Untested Bold Claim → Popperian Falsification**: Does the idea make\n"
            "   a bold, specific, testable claim that has NOT been subjected to\n"
            "   rigorous attempted refutation? Evidence: {the specific claim}\n"
            "8. **Observable Pattern → Baconian Inductivism**: Does the idea present\n"
            "   observable instances, cases, or data from which general principles\n"
            "   could be systematically extracted? Evidence: {the observable pattern}\n"
            "\n"
            "## Phase 3: Select Modes\n"
            "\n"
            "Selection procedure (these are firm, not suggestions):\n"
            "- Diagnose along ALL 8 dimensions, citing evidence from the idea.\n"
            "- Select the TOP 3 most applicable modes based on diagnostic strength.\n"
            "- **Default**: If no strong match on any dimension, default to\n"
            "  Peircean Abduction — every idea has SOMETHING unexplained.\n"
            "- **Mutual exclusion**: Popper and Bacon may NOT both be selected.\n"
            "  If both score highly, select the one with stronger evidence and\n"
            "  replace the other with the next-strongest mode.\n"
            "- For each selected mode, generate exactly 4 ideas (12 total).\n"
            "\n"
            "## Phase 4: Generate\n"
            "\n"
            "For each of the 3 chosen modes, generate exactly 4 ideas (12 total).\n"
            "Each idea must trace back to a specific diagnostic finding from Phase 2.\n"
            "\n"
            "**Pyrrhonian Skepticism**: Suspend judgement on contested claims;\n"
            "  generate ideas that emerge from withholding assent.\n"
            "**Peircean Abduction**: Form explanatory hypotheses for the anomaly;\n"
            "  generate ideas via observe → hypothesize → predict → validate.\n"
            "**Hegelian Dialectics**: Synthesize the contradiction into a higher\n"
            "  unity; generate ideas from thesis-antithesis-synthesis.\n"
            "**Catuṣkoṭi**: Explore all four logical corners (is, is-not,\n"
            "  both, neither); generate ideas from non-binary positions.\n"
            "**Aristotelian Four Causes**: Fill in the missing causes;\n"
            "  generate ideas by completing the causal picture.\n"
            "**Deweyan Inquiry**: Transform the indeterminate situation into a\n"
            "  determinate one; generate ideas via problem-formulation.\n"
            "**Popperian Falsification**: Design severe tests for the bold claim;\n"
            "  generate ideas that would survive attempted refutation.\n"
            "**Baconian Inductivism**: Systematically catalogue instances and\n"
            "  extract general principles; generate ideas via inductive tables.\n"
            "\n"
            "## Phase 5: Save and Report\n"
            "\n"
            "For each generated idea, save it:\n"
            f'  mcp__ontology-server__create_idea with author "AI", parent {ctx.idea_id},\n'
            '  tags ["epi-ralph", "auto", "<mode-name-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            # ── Layer 4: Output Format ────────────────────────────────────
            "Format:\n"
            "\n"
            "# Generated Ideas — Auto Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            "**Modes**: {comma-separated list of 3 chosen modes}\n"
            "\n"
            "## Diagnosis\n"
            "| Diagnostic Question | Mode Indicated | Evidence | Strength |\n"
            "|---------------------|---------------|----------|----------|\n"
            "| Contested Claims | Pyrrhonian Skepticism | {evidence or N/A} | {strong/moderate/weak/N/A} |\n"
            "| Unexplained Anomaly | Peircean Abduction | {evidence or N/A} | {strong/moderate/weak/N/A} |\n"
            "| Genuine Contradiction | Hegelian Dialectics | {evidence or N/A} | {strong/moderate/weak/N/A} |\n"
            "| Non-Binary Tension | Catuṣkoṭi | {evidence or N/A} | {strong/moderate/weak/N/A} |\n"
            "| Unclear Purpose/Composition | Aristotelian Four Causes | {evidence or N/A} | {strong/moderate/weak/N/A} |\n"
            "| Indeterminate Situation | Deweyan Inquiry | {evidence or N/A} | {strong/moderate/weak/N/A} |\n"
            "| Untested Bold Claim | Popperian Falsification | {evidence or N/A} | {strong/moderate/weak/N/A} |\n"
            "| Observable Pattern | Baconian Inductivism | {evidence or N/A} | {strong/moderate/weak/N/A} |\n"
            "\n"
            "## Mode Prescription\n"
            "| Mode | Diagnostic Basis | Selection Rationale |\n"
            "|------|-----------------|---------------------|\n"
            "| {philosopher-grounded mode} | {which diagnostic finding} | {why this mode fits} |\n"
            "| ... | ... | ... |\n"
            "\n"
            "## Idea 1: {Title}\n"
            "**Mode**: {philosopher-grounded mode}\n"
            "**Diagnostic Basis**: {which Phase 2 finding drives this}\n"
            "**Source Ideas**: {root + any pool ideas used}\n"
            "**Description**: {2-3 sentences}\n"
            "**Novelty**: {why distinct from existing ideas}\n"
            "\n"
            "## Idea 2: ...\n"
            "...\n"
            "## Idea 12: ...\n"
            "\n"
            # ── Layer 5: Anti-Collapse Guard ──────────────────────────────
            "## CRITICAL ANTI-COLLAPSE RULES\n"
            "- Do NOT select modes based on which sounds most interesting —\n"
            "  select based on the EPISTEMOLOGICAL SITUATION of the idea.\n"
            "- If you cannot cite specific evidence from the idea for a\n"
            "  diagnosis, that diagnosis is WRONG. Mark it N/A.\n"
            "- Fallback: If no strong match, default to Peircean Abduction.\n"
            "- NEVER select more than 3 modes.\n"
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
            self.phase_id, "auto", ctx, raw, _OUTPUT_FILE, _ALL_FRAMEWORKS,
        )
