"""Epistemology Pool mode — structural pool analysis and gap-filling.

The pool mode's distinctive process is *cartographic*: it maps the entire
idea pool as a landscape before generating.  The analysis (cluster map,
gap inventory, assumption census) IS the mode — generation follows from
the map, not from a single idea.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = ["Gap Analysis", "Conceptual Combination", "Assumption Inversion"]
_OUTPUT_FILE = "ep-pool-ideas.md"


class PoolPhase(Phase[EpistemologyOutput]):
    """Epistemology pool mode: map the pool landscape, then fill its gaps."""

    phase_id: str = "ep-pool"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Pool Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your job is to SEE THE POOL AS A WHOLE and generate ideas that the pool\n"
            "is missing. You are a cartographer, not an expander of single ideas.\n"
            "\n"
            "## Phase 1: Survey the Landscape\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            "2. Query ALL ideas in the pool: mcp__ontology-server__query_ideas\n"
            "   Do multiple queries if needed to get full coverage.\n"
            "3. For each idea, note: its domain, its key claim, and which other ideas\n"
            "   it connects to (shared tags, references, similar domains).\n"
            "\n"
            "## Phase 2: Draw the Map\n"
            "\n"
            "Before generating anything, write a structural analysis:\n"
            "\n"
            "- **Cluster map**: Group ideas into 3-6 thematic clusters. Name each\n"
            "  cluster and list its members. Two ideas are in the same cluster if\n"
            "  they share a domain, build on each other, or address the same concern.\n"
            "- **Gap inventory**: What connections SHOULD exist between clusters but\n"
            "  don't? What topics are conspicuously absent? Where is the pool thin?\n"
            "- **Assumption census**: What assumptions are shared across 3+ ideas?\n"
            "  These are the pool's unexamined foundations.\n"
            "\n"
            "## Phase 3: Select the Root\n"
            "\n"
            "Choose the **most promising idea** as the generative root — not the\n"
            "best idea, but the one sitting at the richest intersection of gaps.\n"
            "The root should be the idea from which new ideas can bridge the most\n"
            "missing connections. Explain why you chose it.\n"
            "\n"
            "## Phase 4: Generate\n"
            "\n"
            "Generate exactly 3 ideas, one per protocol. Each idea must directly\n"
            "address something found in Phase 2:\n"
            "\n"
            "**Gap Analysis**: Pick a specific gap from your gap inventory.\n"
            "Create an idea that bridges it. Name the clusters it connects.\n"
            "\n"
            "**Conceptual Combination**: Pick two ideas from DIFFERENT clusters\n"
            "that have no existing connection. What idea lives at their intersection?\n"
            "Be specific about what each parent contributes.\n"
            "\n"
            "**Assumption Inversion**: Pick a specific assumption from your census.\n"
            "State it explicitly, then negate it. What idea becomes possible when\n"
            "that assumption is dropped? Name which ideas would be affected.\n"
            "\n"
            "## Phase 5: Save and Report\n"
            "\n"
            "For each generated idea, save it:\n"
            '  mcp__ontology-server__create_idea with author "AI",\n'
            '  tags ["epi-ralph", "pool", "<protocol-name-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            "Format:\n"
            "\n"
            "# Generated Ideas — Pool Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            f"**Frameworks**: {', '.join(_FRAMEWORKS)}\n"
            "\n"
            "## Pool Landscape\n"
            "### Clusters\n"
            "{cluster name}: {idea ids and one-line descriptions}\n"
            "### Gaps\n"
            "{numbered list of missing connections}\n"
            "### Shared Assumptions\n"
            "{numbered list with which ideas share each}\n"
            "\n"
            "## Root Selection\n"
            "**Selected Root**: {idea id and title}\n"
            "**Rationale**: {why this idea sits at the richest intersection}\n"
            "\n"
            "## Idea 1: {Title}\n"
            "**Protocol**: Gap Analysis\n"
            "**Gap Addressed**: {which gap from the inventory}\n"
            "**Clusters Bridged**: {which clusters this connects}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Idea 2: {Title}\n"
            "**Protocol**: Conceptual Combination\n"
            "**Parent Ideas**: {idea A from cluster X} + {idea B from cluster Y}\n"
            "**From A**: {what A contributes}\n"
            "**From B**: {what B contributes}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Idea 3: {Title}\n"
            "**Protocol**: Assumption Inversion\n"
            "**Assumption Challenged**: {the specific assumption, stated explicitly}\n"
            "**Ideas Affected**: {which ideas rest on this assumption}\n"
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
            self.phase_id, "pool", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
