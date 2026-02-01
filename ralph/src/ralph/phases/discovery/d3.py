"""D3 Phase – Value Mapping.

Implements the third discovery sub-phase that assesses business value,
strategic fit, and ROI potential for a given idea.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import D3Output


class D3Phase(Phase[D3Output]):
    """D3: Value Mapping phase.

    Constructs a prompt that asks Claude to assess business value, strategic
    fit, and ROI potential, writing findings to ``d3-value-mapping.md``
    inside the work directory.  Reads ``d1-inventory.md`` and
    ``d2-personas.md`` from previous phases.
    """

    phase_id: str = "d3"
    timeout_s: float = 1200.0  # 20 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the D3 value mapping prompt, ported from discovery-ralph.sh."""
        output_file = ctx.work_dir / "d3-value-mapping.md"
        d1_file = ctx.work_dir / "d1-inventory.md"
        d2_file = ctx.work_dir / "d2-personas.md"
        discovery_date = date.today().isoformat()

        return (
            f"You are conducting Phase D3: Value Mapping for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Assess business value, strategic fit, and ROI potential.\n"
            "\n"
            "## Context\n"
            f"- Read the idea: mcp__idea-pool__read_idea with identifier {ctx.idea_id}\n"
            f"- Read inventory: {d1_file}\n"
            f"- Read personas: {d2_file}\n"
            "\n"
            "## Instructions\n"
            "\n"
            "1. Assess the idea against multiple value dimensions\n"
            "2. Consider strategic fit with existing systems/goals\n"
            "3. Estimate effort vs. impact\n"
            "\n"
            f"Write to: {output_file}\n"
            "\n"
            "Structure:\n"
            "\n"
            "# D3: Value Mapping\n"
            f"**Idea**: {ctx.idea_id}\n"
            f"**Date**: {discovery_date}\n"
            "**Time-box**: 20 minutes\n"
            "\n"
            "## Value Dimensions\n"
            "\n"
            "### User Value\n"
            "| Dimension | Rating (1-5) | Evidence |\n"
            "|-----------|--------------|----------|\n"
            "| Pain reduction | ... | From D2: [specific pain] |\n"
            "| Time savings | ... | ... |\n"
            "| Quality improvement | ... | ... |\n"
            "| New capability | ... | ... |\n"
            "\n"
            "**User value score**: X/20\n"
            "\n"
            "### Business Value\n"
            "| Dimension | Rating (1-5) | Rationale |\n"
            "|-----------|--------------|----------|\n"
            "| Revenue potential | ... | ... |\n"
            "| Cost reduction | ... | ... |\n"
            "| Competitive advantage | ... | ... |\n"
            "| Strategic alignment | ... | ... |\n"
            "\n"
            "**Business value score**: X/20\n"
            "\n"
            "### Technical Value\n"
            "| Dimension | Rating (1-5) | Rationale |\n"
            "|-----------|--------------|----------|\n"
            "| Reusability | ... | ... |\n"
            "| Technical debt reduction | ... | ... |\n"
            "| Platform enhancement | ... | ... |\n"
            "| Learning/capability building | ... | ... |\n"
            "\n"
            "**Technical value score**: X/20\n"
            "\n"
            "## Effort vs. Impact Matrix\n"
            "\n"
            "**Estimated Effort**: [Low/Medium/High]\n"
            "**Estimated Impact**: [Low/Medium/High]\n"
            "**Quadrant**: [Quick Win / Major Project / Fill-in / Thankless Task]\n"
            "\n"
            "## Strategic Fit\n"
            "\n"
            "**Alignment with existing systems**:\n"
            "- [System 1]: [how it fits]\n"
            "\n"
            "## ROI Assessment\n"
            "\n"
            "**ROI verdict**: [Strong / Moderate / Weak / Negative]\n"
            "\n"
            "## Value Summary\n"
            "\n"
            "**Total value score**: X/60\n"
            "**Priority recommendation**: [P0-Critical / P1-High / P2-Medium / P3-Low]\n"
            "**Confidence**: [High/Medium/Low]\n"
            "\n"
            "Think like a product strategist. Be honest about value and effort."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during D3."""
        return [
            {"name": "mcp__idea-pool__read_idea"},
            {"name": "Read"},
            {"name": "Write"},
        ]

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        """Invoke Claude.

        The base framework will provide a concrete adapter; this default
        raises NotImplementedError to signal that a real adapter is needed.
        """
        raise NotImplementedError(
            "D3Phase.run_claude requires a Claude adapter to be injected"
        )

    def parse_output(self, ctx: PhaseContext, raw: Any) -> D3Output:
        """Parse D3 output by reading ``d3-value-mapping.md`` from *work_dir*.

        Extracts total value score and quadrant from the markdown content.
        Raises :class:`ParseError` if the value mapping file is missing.
        """
        value_mapping_file = ctx.work_dir / "d3-value-mapping.md"

        if not value_mapping_file.exists():
            raise ParseError(
                f"d3-value-mapping.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = value_mapping_file.read_text(encoding="utf-8")

        total_value_score = _extract_total_value_score(content)
        quadrant = _extract_quadrant(content)

        return D3Output(
            value_mapping_file=value_mapping_file,
            total_value_score=total_value_score,
            quadrant=quadrant,
        )

    def get_timeout_seconds(self) -> float:
        """Return the D3 timeout in seconds (20 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_total_value_score(content: str) -> int:
    """Extract the total value score (X/60) from the markdown content."""
    match = re.search(r"\*\*Total value score\*\*:\s*(\d+)/60", content)
    return int(match.group(1)) if match else 0


def _extract_quadrant(content: str) -> str:
    """Extract the effort-impact quadrant from the markdown content."""
    match = re.search(
        r"\*\*Quadrant\*\*:\s*(.+)",
        content,
    )
    if match:
        return match.group(1).strip()
    return "Unknown"
