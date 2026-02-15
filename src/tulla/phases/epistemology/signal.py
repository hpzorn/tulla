"""Epistemology Signal mode — external signal detection and integration.

The signal mode's distinctive process is *reactive*: it begins with the
outside world and lets external developments drive idea generation.
Unlike domain mode (which researches a known domain), signal mode casts a
wide net and follows whatever it catches.  The signal is the protagonist —
the pool is the context it lands in.
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
    """Epistemology signal mode: catch external signals, integrate with pool."""

    phase_id: str = "ep-signal"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / _OUTPUT_FILE
        run_date = date.today().isoformat()

        return (
            f"You are Epistemology Ralph — Signal Mode for idea {ctx.idea_id}.\n"
            "\n"
            "Your job is to be the pool's ANTENNA. You detect what is happening\n"
            "in the world right now and bring it back as raw material. The external\n"
            "signal drives everything — you do not start from the pool.\n"
            "\n"
            "## Phase 1: Understand the Context\n"
            "\n"
            f"1. Read idea {ctx.idea_id}: mcp__ontology-server__get_idea\n"
            "   This gives you the FREQUENCY to tune to — the domain and concerns\n"
            "   that determine what counts as a relevant signal.\n"
            "\n"
            "## Phase 2: Signal Detection (this is the core of the mode)\n"
            "\n"
            "Cast a wide net. You are looking for things the pool does NOT already\n"
            "know — recent developments, shifts, surprises.\n"
            "\n"
            "2. Use WebSearch broadly — at least 3 searches:\n"
            "   - Recent news/developments in the idea's space\n"
            "   - Emerging trends or technologies that could disrupt it\n"
            "   - Surprising failures or successes in adjacent areas\n"
            "\n"
            "3. For the most interesting results, use WebFetch to read them\n"
            "   in depth. You need SUBSTANCE, not headlines.\n"
            "\n"
            "4. From all your research, identify exactly 3 SIGNALS — concrete,\n"
            "   specific developments (not vague trends). For each signal:\n"
            "   - **What happened**: specific event, publication, announcement, or shift\n"
            "   - **When**: as specific as possible\n"
            "   - **Why it matters**: what does this change or threaten or enable?\n"
            "   - **Signal strength**: strong (confirmed, multiple sources) / medium\n"
            "     (single source, credible) / weak (speculative, early)\n"
            "\n"
            "## Phase 3: Pool Impact Assessment\n"
            "\n"
            "5. Query the pool: mcp__ontology-server__query_ideas\n"
            "6. For each of your 3 signals, assess its impact on the pool:\n"
            "   - Which existing ideas does this signal affect?\n"
            "   - Does it validate, threaten, or transform them?\n"
            "   - What new possibility does it open that the pool hasn't considered?\n"
            "\n"
            "## Phase 4: Generate from Signals\n"
            "\n"
            "Generate exactly 3 ideas, one per signal. For each, choose the most\n"
            "fitting integration type:\n"
            "\n"
            "**Extension**: The signal confirms a direction — push it further.\n"
            "What becomes possible NOW that wasn't before this signal?\n"
            "\n"
            "**Challenge**: The signal threatens an assumption — confront it.\n"
            "What if this signal means an existing idea is wrong?\n"
            "\n"
            "**Application**: The signal is a tool — apply it to a pool idea.\n"
            "How does this specific development change what we can build?\n"
            "\n"
            "**Combination**: The signal completes a puzzle — combine it with\n"
            "pool knowledge to produce something neither had alone.\n"
            "\n"
            "## Phase 5: Save and Report\n"
            "\n"
            "For each generated idea, save it:\n"
            '  mcp__ontology-server__create_idea with author "AI",\n'
            '  tags ["epi-ralph", "signal", "<integration-type-lowercase>"]\n'
            "\n"
            f"Write the full report to: {output_file}\n"
            "\n"
            "Format:\n"
            "\n"
            "# Generated Ideas — Signal Mode\n"
            f"**Root Idea**: {ctx.idea_id}\n"
            f"**Date**: {run_date}\n"
            "**Frameworks**: {comma-separated list of chosen integration types}\n"
            "\n"
            "## Signal 1: {headline}\n"
            "**What**: {specific event or development}\n"
            "**When**: {date or timeframe}\n"
            "**Strength**: {strong/medium/weak}\n"
            "**Source**: {URL or reference}\n"
            "**Pool Impact**: {which ideas affected and how}\n"
            "\n"
            "## Signal 2: ...\n"
            "## Signal 3: ...\n"
            "\n"
            "## Idea 1: {Title}\n"
            "**Protocol**: {integration type}\n"
            "**Signal**: {which signal drives this}\n"
            "**Pool Ideas Involved**: {which existing ideas}\n"
            "**Description**: {2-3 sentences}\n"
            "**Novelty**: {what this adds that neither signal nor pool had}\n"
            "\n"
            "## Idea 2: ...\n"
            "## Idea 3: ...\n"
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
