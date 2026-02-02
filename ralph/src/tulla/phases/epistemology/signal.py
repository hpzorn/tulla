"""Epistemology Signal mode — weak-signal scan.

Detects weak signals in the idea pool and codebase that may indicate
emerging patterns, risks, or opportunities not yet captured in ideas.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import SignalOutput


class SignalPhase(Phase[SignalOutput]):
    """Epistemology signal mode: detect weak signals and emerging patterns."""

    phase_id: str = "ep-signal"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / "ep-signals.md"
        run_date = date.today().isoformat()

        return (
            f"You are conducting Epistemology — Weak Signal Scan for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Detect weak signals in the idea pool and codebase that may indicate "
            "emerging patterns, risks, or opportunities not yet captured.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: mcp__idea-pool__read_idea with identifier {ctx.idea_id}\n"
            "2. Query the broader pool: mcp__idea-pool__query_ideas\n"
            "3. Recall recent facts: mcp__ontology-server__recall_recent_facts\n"
            "4. Scan the codebase for patterns using Glob/Grep\n"
            "5. Look for:\n"
            "   - Recurring themes across unrelated ideas\n"
            "   - Patterns in what gets stuck or blocked\n"
            "   - Emerging capabilities that aren't being leveraged\n"
            "   - Risks mentioned in passing but not addressed\n"
            "   - Opportunities at the intersection of multiple ideas\n"
            "\n"
            f"6. Write findings to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # Epistemology: Weak Signals\n"
            f"   **Idea context**: {ctx.idea_id}\n"
            f"   **Date**: {run_date}\n"
            "\n"
            "   ## Signals Detected\n"
            "   | # | Signal | Source | Strength | Actionable? |\n"
            "   |---|--------|--------|----------|-------------|\n"
            "\n"
            "   ## Emerging Patterns\n"
            "   [Recurring themes or trends across the pool]\n"
            "\n"
            "   ## Latent Risks\n"
            "   [Risks mentioned but not yet tracked]\n"
            "\n"
            "   ## Untapped Opportunities\n"
            "   [Capabilities or intersections not being leveraged]\n"
            "\n"
            "   ## Recommendations\n"
            "   [Which signals warrant new ideas or immediate action]\n"
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return [
            {"name": "mcp__idea-pool__read_idea"},
            {"name": "mcp__idea-pool__query_ideas"},
            {"name": "mcp__ontology-server__recall_facts"},
            {"name": "mcp__ontology-server__recall_recent_facts"},
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
            {"name": "Grep"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> SignalOutput:
        output_file = ctx.work_dir / "ep-signals.md"

        if not output_file.exists():
            raise ParseError(
                f"ep-signals.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        signals_section = _extract_section(content, "Signals Detected")
        signals_detected = _count_table_rows(signals_section)

        # Count actionable signals (rows with "Yes" in Actionable column)
        actionable_signals = 0
        for line in signals_section.strip().splitlines():
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                cells = [c.strip() for c in stripped.split("|")]
                for cell in cells:
                    if cell.lower() in ("yes", "true", "y"):
                        actionable_signals += 1
                        break

        return SignalOutput(
            output_file=output_file,
            signals_detected=signals_detected,
            actionable_signals=actionable_signals,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_section(content: str, heading: str) -> str:
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else ""


def _count_table_rows(section: str) -> int:
    rows = 0
    for line in section.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\|[\s-]+\|", stripped):
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            rows += 1
    return max(0, rows - 1) if rows > 0 else 0
