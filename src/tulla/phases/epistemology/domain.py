"""Epistemology Domain mode — analogical transfer with web research.

Extracts the domain from the idea context, uses web search for recent
developments, and generates ideas via Gap Analysis, Analogical Transfer,
and Assumption Inversion.
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
    """Epistemology domain mode: domain-focused exploration with analogical transfer."""

    phase_id: str = "ep-domain"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Domain Mode, exploring the domain of idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Identify the idea's domain, research recent developments, and generate "
            "new ideas via analogical transfer and gap analysis.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "2. Infer the primary domain from the idea's content\n"
            "3. Use WebSearch to find recent developments, unsolved problems, and\n"
            "   breakthroughs in this domain\n"
            "4. Query the pool: mcp__ontology-server__query_ideas to find ideas\n"
            "   related to this domain\n"
            "\n"
            "5. Generate exactly 3 new ideas, one per protocol:\n"
            "\n"
            "   **Gap Analysis**: What unexplored areas exist in this domain?\n"
            "   What questions are no one asking? What niches are underserved?\n"
            "\n"
            "   **Analogical Transfer**: What solutions from *other* fields could\n"
            "   be applied here? Look for structural similarities with distant domains.\n"
            "\n"
            "   **Assumption Inversion**: What current approaches in this domain\n"
            "   rest on assumptions that could be wrong? What if we reversed them?\n"
            "\n"
            "6. For each generated idea, save it to the pool:\n"
            '   mcp__ontology-server__create_idea with author "AI",\n'
            '   tags ["epi-ralph", "domain", "<protocol-name-lowercase>"]\n'
            "\n"
            f"7. Write the full report to: {output_file}\n"
            "\n"
            "   Use this format:\n"
            "\n"
            "   # Generated Ideas — Domain Mode\n"
            f"   **Root Idea**: {ctx.idea_id}\n"
            f"   **Date**: {run_date}\n"
            f"   **Frameworks**: {', '.join(_FRAMEWORKS)}\n"
            "\n"
            "   ## Idea 1: {Title}\n"
            "   **Protocol**: Gap Analysis\n"
            "   **Source Ideas**: {which existing ideas inspired this}\n"
            "   **Description**: {2-3 sentences}\n"
            "   **Novelty**: {why this is distinct from existing ideas}\n"
            "\n"
            "   ## Idea 2: ...\n"
            "   ## Idea 3: ...\n"
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
