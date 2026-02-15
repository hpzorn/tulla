"""Epistemology Idea mode — idea-focused expansion protocols.

Reads the source idea and related ideas, then generates new ideas using
Extension, Lateral Transfer, Assumption Inversion, Decomposition, and
Synthesis protocols.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = [
    "Extension",
    "Lateral Transfer",
    "Assumption Inversion",
    "Decomposition",
    "Synthesis",
]
_OUTPUT_FILE = "ep-idea-ideas.md"


class IdeaPhase(Phase[EpistemologyOutput]):
    """Epistemology idea mode: expand an idea via philosophical protocols."""

    phase_id: str = "ep-idea"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Idea Mode, expanding idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Read the source idea and its neighbours, then generate new ideas "
            "using philosophical expansion protocols.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "2. Find related ideas: mcp__ontology-server__query_ideas\n"
            "3. Get direct neighbours: mcp__ontology-server__get_related_ideas\n"
            "\n"
            "4. Generate exactly 3 new ideas. Choose the 3 most fitting protocols from:\n"
            "\n"
            "   **Extension**: Push the idea further in its natural direction.\n"
            "   What is the logical next step if we take this idea seriously?\n"
            "\n"
            "   **Lateral Transfer**: Apply the core insight to a completely different domain.\n"
            "   Where else could this principle create value?\n"
            "\n"
            "   **Assumption Inversion**: Reverse a key assumption of the idea.\n"
            "   What if the opposite assumption were true? What new idea emerges?\n"
            "\n"
            "   **Decomposition**: Break the idea into standalone sub-ideas.\n"
            "   Which component could be an independent, valuable idea on its own?\n"
            "\n"
            "   **Synthesis**: Combine with a related idea from the pool.\n"
            "   What higher-order idea emerges from merging these two?\n"
            "\n"
            "5. For each generated idea, save it to the pool:\n"
            f'   mcp__ontology-server__create_idea with author "AI", parent {ctx.idea_id},\n'
            '   tags ["epi-ralph", "idea", "<protocol-name-lowercase>"]\n'
            "\n"
            f"6. Write the full report to: {output_file}\n"
            "\n"
            "   Use this format:\n"
            "\n"
            "   # Generated Ideas — Idea Mode\n"
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
            {"name": "mcp__ontology-server__get_related_ideas"},
            {"name": "mcp__ontology-server__create_idea"},
            {"name": "Write"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> EpistemologyOutput:
        return parse_epistemology_output(
            self.phase_id, "idea", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
