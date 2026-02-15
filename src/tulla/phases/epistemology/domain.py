"""Epistemology Domain mode — outside-in domain exploration.

The domain mode's distinctive process is *outward-looking*: it starts from
the external world (web research) and works inward to the pool.  The web
research is not a step — it IS the mode.  Ideas emerge from the collision
between what the world knows and what the pool contains.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = ["Gap Analysis", "Analogical Transfer", "Assumption Inversion"]
_OUTPUT_FILE = "ep-domain-ideas.md"


class DomainPhase(Phase[EpistemologyOutput]):
    """Epistemology domain mode: research the domain, then confront pool with findings."""

    phase_id: str = "ep-domain"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Domain Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your job is to bring the OUTSIDE WORLD into the pool. You are a scout\n"
            "returning from the frontier with news that changes everything.\n"
            "\n"
            "## Phase 1: Identify the Domain\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            "2. Identify the idea's primary domain. Be specific — not 'technology'\n"
            "   but 'edge computing for IoT' or 'knowledge graph construction'.\n"
            "   State the domain explicitly before proceeding.\n"
            "\n"
            "## Phase 2: Domain Research (this is the core of the mode)\n"
            "\n"
            "Conduct substantial web research. This is NOT optional background —\n"
            "the research findings ARE your raw material for generation.\n"
            "\n"
            "3. Use WebSearch at least 3 times with different angles:\n"
            "   - Recent breakthroughs or developments in the domain\n"
            "   - Unsolved problems or open questions\n"
            "   - How other fields are approaching similar challenges\n"
            "\n"
            "For each search, record:\n"
            "- What you searched for and why\n"
            "- The key findings (specific facts, names, dates)\n"
            "- What surprised you or contradicted your expectations\n"
            "\n"
            "## Phase 3: Confront Pool with Findings\n"
            "\n"
            "4. Query the pool: mcp__ontology-server__query_ideas for ideas in or\n"
            "   near this domain.\n"
            "5. For each finding from Phase 2, ask: does the pool know this?\n"
            "   Build a confrontation table:\n"
            "   - {finding} → pool has it / pool is behind / pool contradicts / pool is blind\n"
            "\n"
            "## Phase 4: Generate from the Confrontation\n"
            "\n"
            "Generate exactly 3 ideas. Each must cite a specific research finding\n"
            "from Phase 2 AND a specific pool gap from Phase 3:\n"
            "\n"
            "**Gap Analysis**: Where the pool is *blind* — the domain has moved on\n"
            "but the pool doesn't know it yet. What idea brings the pool up to date?\n"
            "Cite the specific external finding and the pool's blind spot.\n"
            "\n"
            "**Analogical Transfer**: Where *another field* solved a problem the\n"
            "domain still struggles with. Name the source field, the solution, and\n"
            "how it maps. Not vague analogy — structural correspondence.\n"
            "\n"
            "**Assumption Inversion**: Where the domain's conventional wisdom is\n"
            "being challenged by recent developments. What if the challengers are\n"
            "right? Cite the specific challenge found in research.\n"
            "\n"
            "## Phase 5: Save and Report\n"
            "\n"
            "For each generated idea, save it:\n"
            '  mcp__ontology-server__create_idea with author "AI",\n'
            '  tags ["epi-ralph", "domain", "<protocol-name-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            "Format:\n"
            "\n"
            "# Generated Ideas — Domain Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            f"**Frameworks**: {', '.join(_FRAMEWORKS)}\n"
            "**Domain**: {the specific domain identified}\n"
            "\n"
            "## Research Log\n"
            "### Search 1: {query}\n"
            "**Key Findings**: {specific facts}\n"
            "**Surprise**: {what was unexpected}\n"
            "### Search 2: ...\n"
            "### Search 3: ...\n"
            "\n"
            "## Pool Confrontation\n"
            "| Finding | Pool Status | Implication |\n"
            "|---------|-------------|-------------|\n"
            "\n"
            "## Idea 1: {Title}\n"
            "**Protocol**: Gap Analysis\n"
            "**External Finding**: {what the world knows}\n"
            "**Pool Blind Spot**: {what the pool is missing}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Idea 2: {Title}\n"
            "**Protocol**: Analogical Transfer\n"
            "**Source Field**: {where the solution comes from}\n"
            "**Source Solution**: {what they did}\n"
            "**Structural Mapping**: {how it applies here}\n"
            "**Description**: {2-3 sentences}\n"
            "\n"
            "## Idea 3: {Title}\n"
            "**Protocol**: Assumption Inversion\n"
            "**Conventional Wisdom**: {what the domain assumes}\n"
            "**Challenge Found**: {the specific counter-evidence}\n"
            "**Description**: {2-3 sentences}\n"
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
            self.phase_id, "domain", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
