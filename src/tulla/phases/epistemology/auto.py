"""Epistemology Auto mode — diagnostic framework selection.

The auto mode's distinctive process is *meta-epistemological*: it analyses
the idea's properties to determine which thinking strategies would be most
productive, then applies them.  It is the only mode that begins with a
diagnostic step — the framework selection is itself a reasoned act, not
a mechanical dispatch.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_ALL_FRAMEWORKS = [
    "Extension",
    "Lateral Transfer",
    "Assumption Inversion",
    "Decomposition",
    "Synthesis",
    "Gap Analysis",
    "Conceptual Combination",
]
_OUTPUT_FILE = "ep-auto-ideas.md"


class AutoPhase(Phase[EpistemologyOutput]):
    """Epistemology auto mode: diagnose the idea, then select and apply frameworks."""

    phase_id: str = "ep-auto"
    timeout_s: float = 1200.0  # 20 minutes — larger scope

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Auto Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your job is to DIAGNOSE the idea first, then prescribe the right\n"
            "thinking strategies. You are a doctor of ideas — examine before\n"
            "treating.\n"
            "\n"
            "## Phase 1: Examine the Idea\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            f"2. Get neighbours: mcp__ontology-server__get_related_ideas for {ctx.idea_id}\n"
            "3. Query broader pool: mcp__ontology-server__query_ideas\n"
            "\n"
            "## Phase 2: Diagnose\n"
            "\n"
            "Assess the idea along these dimensions. Be specific — cite evidence\n"
            "from what you read:\n"
            "\n"
            "- **Maturity**: seed (just a title/sentence), sapling (has structure\n"
            "  but gaps), tree (well-developed, detailed). Evidence: {what you saw}\n"
            "- **Connectivity**: isolated (0-1 neighbours), connected (2-4),\n"
            "  hub (5+). Evidence: {neighbour count and quality}\n"
            "- **Assumption load**: light (few assumptions), heavy (rests on many\n"
            "  assumptions, some questionable). Evidence: {specific assumptions found}\n"
            "- **Decomposability**: atomic (single concept), compound (2-3 separable\n"
            "  parts), complex (many intertwined parts). Evidence: {what parts you see}\n"
            "- **Domain specificity**: narrow (one domain), bridging (touches 2+\n"
            "  domains), universal (domain-independent principle). Evidence: {domains}\n"
            "\n"
            "## Phase 3: Prescribe Frameworks\n"
            "\n"
            "Based on the diagnosis, select exactly 4 frameworks from:\n"
            "Extension, Lateral Transfer, Assumption Inversion, Decomposition,\n"
            "Synthesis, Gap Analysis, Conceptual Combination\n"
            "\n"
            "Selection rules (these are firm, not suggestions):\n"
            "- Extension requires maturity >= sapling (seeds have no direction yet)\n"
            "- Lateral Transfer requires domain specificity narrow or bridging\n"
            "  (universal ideas have nothing to transfer)\n"
            "- Assumption Inversion requires assumption load >= heavy\n"
            "- Decomposition requires decomposability >= compound\n"
            "- Synthesis requires connectivity >= connected (need neighbours to combine)\n"
            "- Gap Analysis requires connectivity <= connected (hubs don't have gaps)\n"
            "- Conceptual Combination requires access to ideas in different domains\n"
            "\n"
            "If fewer than 4 frameworks qualify, relax the weakest constraint and\n"
            "explain which rule you bent and why.\n"
            "\n"
            "## Phase 4: Generate\n"
            "\n"
            "For each of the 4 chosen frameworks, generate exactly 3 ideas (12 total).\n"
            "Each idea must trace back to a specific diagnostic finding from Phase 2.\n"
            "\n"
            "**Extension**: Push the idea further in its natural direction.\n"
            "**Lateral Transfer**: Apply core insight to a different domain.\n"
            "**Assumption Inversion**: Reverse a specific assumption from the diagnosis.\n"
            "**Decomposition**: Extract a specific component identified in Phase 2.\n"
            "**Synthesis**: Combine with a specific neighbour from Phase 1.\n"
            "**Gap Analysis**: Fill a specific gap visible from the connectivity map.\n"
            "**Conceptual Combination**: Merge with a specific idea from a different domain.\n"
            "\n"
            "## Phase 5: Save and Report\n"
            "\n"
            "For each generated idea, save it:\n"
            f'  mcp__ontology-server__create_idea with author "AI", parent {ctx.idea_id},\n'
            '  tags ["epi-ralph", "auto", "<framework-name-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            "Format:\n"
            "\n"
            "# Generated Ideas — Auto Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            "**Frameworks**: {comma-separated list of 4 chosen frameworks}\n"
            "\n"
            "## Diagnosis\n"
            "| Dimension | Assessment | Evidence |\n"
            "|-----------|-----------|----------|\n"
            "| Maturity | {level} | {evidence} |\n"
            "| Connectivity | {level} | {evidence} |\n"
            "| Assumption Load | {level} | {evidence} |\n"
            "| Decomposability | {level} | {evidence} |\n"
            "| Domain Specificity | {level} | {evidence} |\n"
            "\n"
            "## Framework Prescription\n"
            "| Framework | Qualifying Rule | Diagnostic Basis |\n"
            "|-----------|----------------|------------------|\n"
            "| {name} | {which rule} | {which finding} |\n"
            "| ... | ... | ... |\n"
            "\n"
            "## Idea 1: {Title}\n"
            "**Protocol**: {framework}\n"
            "**Diagnostic Basis**: {which Phase 2 finding drives this}\n"
            "**Source Ideas**: {root + any pool ideas used}\n"
            "**Description**: {2-3 sentences}\n"
            "**Novelty**: {why distinct from existing ideas}\n"
            "\n"
            "## Idea 2: ...\n"
            "...\n"
            "## Idea 12: ...\n"
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
