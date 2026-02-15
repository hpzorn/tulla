"""Epistemology Idea mode — deep idea dissection and expansion.

The idea mode's distinctive process is *intensive*: it goes deep into a
single idea's internal structure before expanding.  The dissection (core
insight extraction, assumption inventory, boundary mapping) determines
which expansion protocols are appropriate — the idea's anatomy drives the
choice, not a generic checklist.
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
    """Epistemology idea mode: dissect one idea's structure, then expand."""

    phase_id: str = "ep-idea"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Idea Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your job is to understand this ONE idea so deeply that expansion\n"
            "becomes obvious. You are a surgeon, not a surveyor.\n"
            "\n"
            "## Phase 1: Dissect the Idea\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            f"2. Get its direct neighbours: mcp__ontology-server__get_related_ideas for {ctx.idea_id}\n"
            "3. Read each neighbour with mcp__ontology-server__get_idea to understand\n"
            "   the local context.\n"
            "\n"
            "Now perform a structural dissection:\n"
            "\n"
            "- **Core insight**: In one sentence, what is the fundamental insight\n"
            "  that makes this idea valuable? Strip away implementation details.\n"
            "- **Key assumptions**: List every assumption the idea rests on.\n"
            "  Mark each as [testable] or [foundational].\n"
            "- **Boundaries**: Where does this idea stop? What is explicitly out\n"
            "  of scope? What domains does it touch but not enter?\n"
            "- **Internal tensions**: Does the idea contain contradictions or\n"
            "  unresolved tensions within itself?\n"
            "- **Maturity assessment**: Is this idea a seed (raw), a sapling\n"
            "  (developing), or a tree (well-developed)? This determines which\n"
            "  protocols fit.\n"
            "\n"
            "## Phase 2: Choose 3 Protocols\n"
            "\n"
            "Based on the dissection, choose the 3 most productive protocols.\n"
            "You MUST justify each choice from what you found:\n"
            "\n"
            "- **Extension** — use when the idea is a sapling with clear growth\n"
            "  direction. Requires: an identifiable natural trajectory.\n"
            "- **Lateral Transfer** — use when the core insight is domain-independent.\n"
            "  Requires: a core insight that abstracts cleanly from its current domain.\n"
            "- **Assumption Inversion** — use when you found a testable assumption\n"
            "  that the idea heavily depends on. Requires: a specific assumption to flip.\n"
            "- **Decomposition** — use when the idea is a tree with separable\n"
            "  components. Requires: at least 2 distinct sub-ideas visible.\n"
            "- **Synthesis** — use when a neighbour idea has a complementary gap.\n"
            "  Requires: a specific neighbour to combine with.\n"
            "\n"
            "Do NOT pick protocols just to fill slots. If only 2 fit well, explain\n"
            "why the third is forced and which you chose as the least-bad option.\n"
            "\n"
            "## Phase 3: Generate\n"
            "\n"
            "For each chosen protocol, generate one idea. Each must trace back\n"
            "to the dissection — cite the specific insight, assumption, boundary,\n"
            "or neighbour that drives it.\n"
            "\n"
            "## Phase 4: Save and Report\n"
            "\n"
            "For each generated idea, save it:\n"
            f'  mcp__ontology-server__create_idea with author "AI", parent {ctx.idea_id},\n'
            '  tags ["epi-ralph", "idea", "<protocol-name-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            "Format:\n"
            "\n"
            "# Generated Ideas — Idea Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            "**Frameworks**: {comma-separated list of 3 chosen protocols}\n"
            "\n"
            "## Dissection\n"
            "**Core Insight**: {one sentence}\n"
            "**Key Assumptions**:\n"
            "  - {assumption} [testable/foundational]\n"
            "  - ...\n"
            "**Boundaries**: {what is in/out of scope}\n"
            "**Internal Tensions**: {if any}\n"
            "**Maturity**: {seed/sapling/tree}\n"
            "\n"
            "## Protocol Selection\n"
            "{For each chosen protocol: which dissection finding justifies it}\n"
            "\n"
            "## Idea 1: {Title}\n"
            "**Protocol**: {name}\n"
            "**Driven By**: {which dissection finding}\n"
            "**Source Ideas**: {root + any neighbours used}\n"
            "**Description**: {2-3 sentences}\n"
            "**Novelty**: {why distinct from existing ideas}\n"
            "\n"
            "## Idea 2: ...\n"
            "## Idea 3: ...\n"
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
