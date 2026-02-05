"""P5 Phase – Research Requests.

Implements the fifth planning sub-phase that determines if implementation
can proceed, or if research is needed first.  Checks both the
implementation plan (P4) for blocked tasks and the persona walkthrough
(P4b) for blocking gaps.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from tulla.core.phase import ParseError, Phase, PhaseContext
from tulla.core.phase_facts import group_upstream_facts
from tulla.phases.planning import PLANNING_IDENTITY, build_northstar_section

from .models import P5Output


class P5Phase(Phase[P5Output]):
    """P5: Research Requests phase.

    Constructs a prompt that asks Claude to check for blockers in P4 and
    P4b, producing either a "ready" or "blocked" status.  Writes findings
    to ``p5-research-requests.md`` inside the work directory.
    """

    phase_id: str = "p5"
    timeout_s: float = 600.0  # 10 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the P5 research requests prompt, ported from planning-tulla.sh."""
        output_file = ctx.work_dir / "p5-research-requests.md"
        p4_file = ctx.work_dir / "p4-implementation-plan.md"
        p4b_file = ctx.work_dir / "p4b-persona-walkthrough.md"
        planning_date = date.today().isoformat()

        raw_facts = ctx.config.get("upstream_facts", [])
        grouped = group_upstream_facts(raw_facts)
        northstar_section = build_northstar_section(grouped)
        upstream_section = ""
        if grouped:
            upstream_section = (
                "## Upstream Facts\n"
                f"{json.dumps(grouped, indent=2)}\n"
                "\n"
            )

        return (
            PLANNING_IDENTITY
            + f"## Phase P5: Research Requests\n"
            f"**Idea**: {ctx.idea_id}\n"
            "\n"
            f"{northstar_section}"
            f"{upstream_section}"
            "## Goal\n"
            "Determine if implementation can proceed, or if research is needed first.\n"
            "\n"
            "## Context\n"
            "Read BOTH of these:\n"
            f"- Implementation plan: {p4_file} — look for the 'Blocked Tasks (Need Research)' section.\n"
            f"- Persona walkthrough: {p4b_file} — look for 'Blocking Gaps' and the verdict line.\n"
            "\n"
            "The implementation is BLOCKED if EITHER source has blockers:\n"
            "- P4 has blocked tasks needing research, OR\n"
            "- P4b found blocking persona gaps (WALKTHROUGH_GAPS with blocking items)\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"Write to: {output_file}\n"
            "\n"
            "If NO blocked tasks (table is empty):\n"
            "\n"
            "   # P5: Research Requests\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {planning_date}\n"
            "\n"
            "   ## Status: READY TO IMPLEMENT\n"
            "\n"
            "   No blocking unknowns identified. Implementation can proceed.\n"
            "\n"
            "   ## Planning Artifacts\n"
            "   - p1-discovery-context.md\n"
            "   - p2-codebase-analysis.md\n"
            "   - p3-architecture-design.md\n"
            "   - p4-implementation-plan.md\n"
            "\n"
            "   ## Next Step\n"
            "   Execute the implementation plan in p4-implementation-plan.md\n"
            "\n"
            "   ---\n"
            "   ready\n"
            "\n"
            "If BLOCKED tasks exist:\n"
            "\n"
            "   # P5: Research Requests\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {planning_date}\n"
            "\n"
            "   ## Status: BLOCKED - RESEARCH NEEDED\n"
            "\n"
            "   The following unknowns must be resolved before implementation.\n"
            "\n"
            "   ## Research Requests\n"
            "\n"
            "   ### RR1: [Research Request Title]\n"
            "   **Blocking Task**: [Which task from P4]\n"
            "   **Question**: [Specific, answerable question]\n"
            "   **Why We Can't Proceed**: [What breaks without this answer]\n"
            "   **Suggested Approach**: [How research-tulla should investigate]\n"
            "   **Acceptable Answer Format**: [What kind of answer we need]\n"
            "\n"
            "   ## Handoff to Research-Tulla\n"
            "\n"
            f"   Run: `./research-tulla.sh --idea {ctx.idea_id}` with focus on:\n"
            "   - [RR1 question]\n"
            "\n"
            "   After research completes, re-run planning-tulla to update the plan.\n"
            "\n"
            "   ---\n"
            "   blocked\n"
            "\n"
            "Output ONLY 'ready' or 'blocked' on the final line."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during P5."""
        return [
            {"name": "Read"},
            {"name": "Write"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> P5Output:
        """Parse P5 output by reading ``p5-research-requests.md`` from *work_dir*.

        Extracts PRD status (ready/blocked), total requirements from planning
        artifacts, and phases defined.
        Raises :class:`ParseError` if the research requests file is missing.
        """
        prd_file = ctx.work_dir / "p5-research-requests.md"

        if not prd_file.exists():
            raise ParseError(
                f"p5-research-requests.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = prd_file.read_text(encoding="utf-8")

        # Extract status from last lines.
        status = _extract_status(content)

        # Count research requests (### RR headings).
        total_requirements = len(re.findall(r"###\s+RR\d+:", content))

        # Count phases defined as the number of planning artifacts listed.
        artifacts_section = _extract_section(content, "Planning Artifacts")
        phases_defined = len(re.findall(r"^\s*-\s+", artifacts_section, re.MULTILINE))
        if phases_defined == 0:
            # Fallback: count from Handoff section or status-based.
            phases_defined = 5 if status == "blocked" else 4

        return P5Output(
            prd_file=prd_file,
            total_requirements=total_requirements,
            phases_defined=phases_defined,
        )

    def get_timeout_seconds(self) -> float:
        """Return the P5 timeout in seconds (5 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_status(content: str) -> str:
    """Extract the status (ready/blocked) from the last few lines.

    Falls back to 'ready' if no keyword is found.
    """
    last_lines = content.strip().splitlines()[-5:]
    for line in reversed(last_lines):
        lower = line.strip().lower()
        if lower in ("ready", "blocked"):
            return lower
        for keyword in ("ready", "blocked"):
            if keyword in lower:
                return keyword
    return "ready"


def _extract_section(content: str, heading: str) -> str:
    """Extract content under a markdown ``## heading`` until the next heading."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else ""
