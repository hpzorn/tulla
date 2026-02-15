"""Epistemology Problem mode — multi-approach problem solving.

Extracts the core problem from an idea, searches for prior solutions,
and generates solution ideas via Direct approach, Analogical Transfer,
Assumption Inversion, and Decomposition.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = [
    "Direct Approach",
    "Analogical Transfer",
    "Assumption Inversion",
    "Decomposition",
]
_OUTPUT_FILE = "ep-problem-ideas.md"


class ProblemPhase(Phase[EpistemologyOutput]):
    """Epistemology problem mode: generate solution ideas from multiple angles."""

    phase_id: str = "ep-problem"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Problem Mode, solving the problem in idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Extract the core problem from the idea, search for prior solutions, "
            "and generate new solution ideas from multiple philosophical angles.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "2. Extract the core problem or challenge the idea is trying to address\n"
            "3. Search the pool: mcp__ontology-server__query_ideas for prior solutions\n"
            "4. Use WebSearch for external prior art and approaches\n"
            "\n"
            "5. Generate exactly 3 new solution ideas. Choose the 3 most fitting from:\n"
            "\n"
            "   **Direct Approach**: What is the most straightforward solution?\n"
            "   If you had unlimited resources, what would you build?\n"
            "\n"
            "   **Analogical Transfer**: How has a similar problem been solved in\n"
            "   a completely different domain? What can we borrow?\n"
            "\n"
            "   **Assumption Inversion**: What if the problem's premises are wrong?\n"
            "   What if we challenge the constraints instead of solving within them?\n"
            "\n"
            "   **Decomposition**: Can the problem be broken into smaller, independently\n"
            "   solvable parts? Which sub-problem is most tractable?\n"
            "\n"
            "6. For each generated idea, save it to the pool:\n"
            '   mcp__ontology-server__create_idea with author "AI",\n'
            '   tags ["epi-ralph", "problem", "<protocol-name-lowercase>"]\n'
            "\n"
            f"7. Write the full report to: {output_file}\n"
            "\n"
            "   Use this format:\n"
            "\n"
            "   # Generated Ideas — Problem Mode\n"
            f"   **Root Idea**: {ctx.idea_id}\n"
            f"   **Date**: {run_date}\n"
            "   **Frameworks**: {comma-separated list of chosen protocols}\n"
            "\n"
            "   ## Idea 1: {Title}\n"
            "   **Protocol**: {protocol name}\n"
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
            self.phase_id, "problem", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
