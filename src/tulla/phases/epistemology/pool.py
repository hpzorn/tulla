"""Epistemology Pool mode — pool-driven idea generation.

Analyses the idea pool for gaps, clusters, and combination opportunities,
selects the most promising idea as generative root, and generates new ideas
using Gap Analysis, Conceptual Combination, and Assumption Inversion.
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
    """Epistemology pool mode: generate ideas from pool-level analysis."""

    phase_id: str = "ep-pool"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Pool Mode, generating new ideas for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Analyse the idea pool for gaps, clusters, and combination opportunities. "
            "Select the most promising idea as the generative root. "
            "Generate 3 new ideas using philosophical protocols.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the target idea: mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "2. Query the pool: mcp__ontology-server__query_ideas to survey all ideas\n"
            "3. Analyse the pool:\n"
            "   - Identify idea clusters and gaps between them\n"
            "   - Find combination opportunities across domains\n"
            "   - Note shared assumptions that could be challenged\n"
            "4. **Select the most promising idea** as the generative root — the idea\n"
            "   with the highest potential for spawning novel descendants.\n"
            "\n"
            "5. Generate exactly 3 new ideas, one per protocol:\n"
            "\n"
            "   **Gap Analysis**: Fill a missing connection between idea clusters.\n"
            "   What topic or link is conspicuously absent from the pool?\n"
            "\n"
            "   **Conceptual Combination**: Merge ideas from different domains.\n"
            "   Take two ideas that seem unrelated and find their hidden intersection.\n"
            "\n"
            "   **Assumption Inversion**: Challenge a shared assumption across multiple ideas.\n"
            "   What if the opposite were true? What idea emerges?\n"
            "\n"
            "6. For each generated idea, save it to the pool:\n"
            '   mcp__ontology-server__create_idea with author "AI",\n'
            '   tags ["epi-ralph", "pool", "<protocol-name-lowercase>"]\n'
            "\n"
            f"7. Write the full report to: {output_file}\n"
            "\n"
            "   Use this format:\n"
            "\n"
            "   # Generated Ideas — Pool Mode\n"
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
            "   ## Idea 2: {Title}\n"
            "   **Protocol**: Conceptual Combination\n"
            "   ...\n"
            "\n"
            "   ## Idea 3: {Title}\n"
            "   **Protocol**: Assumption Inversion\n"
            "   ...\n"
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
