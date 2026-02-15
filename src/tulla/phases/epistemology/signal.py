"""Epistemology Signal mode — external signal integration.

Reacts to external developments by searching the web for recent signals
relevant to the idea's domain, then generates ideas that extend, challenge,
apply, or combine those signals with existing pool knowledge.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = ["Extension", "Challenge", "Application", "Combination"]
_OUTPUT_FILE = "ep-signal-ideas.md"


class SignalPhase(Phase[EpistemologyOutput]):
    """Epistemology signal mode: integrate external signals with pool ideas."""

    phase_id: str = "ep-signal"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Signal Mode, integrating external signals for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Search for recent external developments relevant to the idea's domain, "
            "then generate new ideas that integrate these signals with existing pool knowledge.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "2. Use WebSearch to find recent developments, news, research, or trends\n"
            "   relevant to the idea's domain\n"
            "3. Use WebFetch to read the most relevant articles in depth\n"
            "4. Query the pool: mcp__ontology-server__query_ideas to find related ideas\n"
            "\n"
            "5. Generate exactly 3 new ideas. Choose the 3 most fitting from these\n"
            "   integration types:\n"
            "\n"
            "   **Extension**: Build on the external signal. If this trend continues,\n"
            "   what new idea becomes possible or necessary?\n"
            "\n"
            "   **Challenge**: Question the signal's assumptions. What if this\n"
            "   development is wrong, overhyped, or solving the wrong problem?\n"
            "\n"
            "   **Application**: Apply the signal to existing pool ideas. How does\n"
            "   this new information change or enhance what we already know?\n"
            "\n"
            "   **Combination**: Synthesise the signal with existing knowledge.\n"
            "   What novel idea emerges from combining external and internal insights?\n"
            "\n"
            "6. For each generated idea, save it to the pool:\n"
            '   mcp__ontology-server__create_idea with author "AI",\n'
            '   tags ["epi-ralph", "signal", "<integration-type-lowercase>"]\n'
            "\n"
            f"7. Write the full report to: {output_file}\n"
            "\n"
            "   Use this format:\n"
            "\n"
            "   # Generated Ideas — Signal Mode\n"
            f"   **Root Idea**: {ctx.idea_id}\n"
            f"   **Date**: {run_date}\n"
            "   **Frameworks**: {comma-separated list of chosen integration types}\n"
            "\n"
            "   ## Idea 1: {Title}\n"
            "   **Protocol**: {integration type}\n"
            "   **Source Ideas**: {which existing ideas + external signals inspired this}\n"
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
            {"name": "WebFetch"},
            {"name": "Write"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> EpistemologyOutput:
        return parse_epistemology_output(
            self.phase_id, "signal", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
