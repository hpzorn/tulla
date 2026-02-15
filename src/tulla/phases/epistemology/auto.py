"""Epistemology Auto mode — automatic framework selection.

Default mode when no ``--mode`` is specified. Reads the idea and its
neighbours, selects the 4 most fitting frameworks from the idea-based set,
and generates 3 ideas per framework (12 total).
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
    """Epistemology auto mode: select 4 frameworks and generate 12 ideas."""

    phase_id: str = "ep-auto"
    timeout_s: float = 1200.0  # 20 minutes — larger scope

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()
        frameworks_list = ", ".join(_ALL_FRAMEWORKS)

        return (
            f"You are Epistemology Ralph — Auto Mode, generating ideas for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Select the 4 most fitting philosophical frameworks for this idea and "
            "generate 3 ideas per framework (12 total). Save all to the pool.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "2. Query related ideas: mcp__ontology-server__query_ideas\n"
            "3. Get direct neighbours: mcp__ontology-server__get_related_ideas\n"
            "\n"
            "4. **Select exactly 4 frameworks** from this list:\n"
            f"   {frameworks_list}\n"
            "\n"
            "   Use these heuristics to choose:\n"
            "   - **Mature ideas** (well-developed, stable) → Extension, Decomposition\n"
            "   - **Isolated ideas** (few connections) → Lateral Transfer, Gap Analysis\n"
            "   - **Ideas with strong assumptions** → Assumption Inversion\n"
            "   - **Ideas with many neighbours** → Synthesis, Conceptual Combination\n"
            "\n"
            "   Explain your selection rationale briefly before generating.\n"
            "\n"
            "5. For each of the 4 chosen frameworks, generate exactly 3 ideas:\n"
            "\n"
            "   **Extension**: Push the idea further in its natural direction.\n"
            "   **Lateral Transfer**: Apply core insight to a different domain.\n"
            "   **Assumption Inversion**: Reverse a key assumption.\n"
            "   **Decomposition**: Break into standalone sub-ideas.\n"
            "   **Synthesis**: Combine with a related pool idea.\n"
            "   **Gap Analysis**: Fill missing connections between clusters.\n"
            "   **Conceptual Combination**: Merge ideas from different domains.\n"
            "\n"
            "6. For each generated idea, save it to the pool:\n"
            f'   mcp__ontology-server__create_idea with author "AI", parent {ctx.idea_id},\n'
            '   tags ["epi-ralph", "auto", "<framework-name-lowercase>"]\n'
            "\n"
            f"7. Write the full report to: {output_file}\n"
            "\n"
            "   Use this format:\n"
            "\n"
            "   # Generated Ideas — Auto Mode\n"
            f"   **Root Idea**: {ctx.idea_id}\n"
            f"   **Date**: {run_date}\n"
            "   **Frameworks**: {comma-separated list of 4 chosen frameworks}\n"
            "\n"
            "   ## Framework Selection Rationale\n"
            "   {Brief explanation of why these 4 frameworks were chosen}\n"
            "\n"
            "   ## Idea 1: {Title}\n"
            "   **Protocol**: {framework name}\n"
            "   **Source Ideas**: {which existing ideas inspired this}\n"
            "   **Description**: {2-3 sentences}\n"
            "   **Novelty**: {why this is distinct from existing ideas}\n"
            "\n"
            "   ## Idea 2: ...\n"
            "   ...\n"
            "   ## Idea 12: ...\n"
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
