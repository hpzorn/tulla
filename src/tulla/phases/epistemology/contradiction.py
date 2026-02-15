"""Epistemology Contradiction mode — Hegelian dialectical synthesis.

Finds ideas that contradict or tension with the source idea, analyses the
core tension, and generates synthesis ideas via Transcendence, Integration,
and Reframing.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tulla.core.phase import Phase, PhaseContext

from ._helpers import parse_epistemology_output
from .models import EpistemologyOutput

_FRAMEWORKS = ["Transcendence", "Integration", "Reframing"]
_OUTPUT_FILE = "ep-contradiction-ideas.md"


class ContradictionPhase(Phase[EpistemologyOutput]):
    """Epistemology contradiction mode: Hegelian dialectical synthesis."""

    phase_id: str = "ep-contradiction"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Contradiction Mode, applying Hegelian dialectics to idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Find ideas that contradict or tension with the source idea, analyse "
            "the core tension, and generate synthesis ideas that transcend the opposition.\n"
            "\n"
            "## CRITICAL WARNING\n"
            "Avoid 'agreeable synthesis' that just says 'do both' — true synthesis "
            "transcends the opposition. A valid synthesis must produce something NEITHER "
            "side had on its own. If you cannot find genuine transcendence, say so.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea (thesis): mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "2. Query the pool: mcp__ontology-server__query_ideas\n"
            "3. Find ideas that contradict, tension with, or oppose the source idea.\n"
            "   These are your antitheses.\n"
            "4. For each contradiction pair, analyse:\n"
            "   - What is the core tension?\n"
            "   - What does each side get right?\n"
            "   - What must be preserved from each?\n"
            "\n"
            "5. Apply **Hegelian dialectical synthesis** to generate exactly 3 synthesis\n"
            "   ideas, each using a different resolution type:\n"
            "\n"
            "   **Transcendence**: Rise above the opposition entirely. Find a vantage\n"
            "   point from which both thesis and antithesis are partial truths of a\n"
            "   larger whole.\n"
            "\n"
            "   **Integration**: Weave the valid kernels of both positions into a\n"
            "   new framework that preserves each side's strengths while eliminating\n"
            "   their weaknesses.\n"
            "\n"
            "   **Reframing**: Dissolve the contradiction by showing it rests on a\n"
            "   false dichotomy. Redefine the terms so the opposition vanishes.\n"
            "\n"
            "6. For each synthesis idea, save it to the pool:\n"
            '   mcp__ontology-server__create_idea with author "AI",\n'
            '   tags ["epi-ralph", "contradiction", "<resolution-type-lowercase>"]\n'
            "\n"
            f"7. Write the full report to: {output_file}\n"
            "\n"
            "   Use this format:\n"
            "\n"
            "   # Generated Ideas — Contradiction Mode\n"
            f"   **Root Idea**: {ctx.idea_id}\n"
            f"   **Date**: {run_date}\n"
            f"   **Frameworks**: {', '.join(_FRAMEWORKS)}\n"
            "\n"
            "   ## Synthesis 1: {Title}\n"
            "   **Resolution Type**: Transcendence\n"
            "   **From Thesis**: {what is preserved from the source idea}\n"
            "   **From Antithesis**: {what is preserved from the opposing idea}\n"
            "   **Novel Contribution**: {what emerges that neither had}\n"
            "   **Source Ideas**: {thesis and antithesis idea identifiers}\n"
            "   **Description**: {2-3 sentences}\n"
            "\n"
            "   ## Synthesis 2: {Title}\n"
            "   **Resolution Type**: Integration\n"
            "   ...\n"
            "\n"
            "   ## Synthesis 3: {Title}\n"
            "   **Resolution Type**: Reframing\n"
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
            self.phase_id, "contradiction", ctx, raw, _OUTPUT_FILE, _FRAMEWORKS,
        )
