"""P4 Phase – Implementation Plan.

Implements the fourth planning sub-phase that creates a detailed,
executable implementation plan with file-level and task-level specificity.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import P4Output


class P4Phase(Phase[P4Output]):
    """P4: Implementation Plan phase.

    Constructs a prompt that asks Claude to create a detailed implementation
    plan, writing it to ``p4-implementation-plan.md`` inside the work
    directory.  Reads ``p1-discovery-context.md``, ``p2-codebase-analysis.md``,
    and ``p3-architecture-design.md`` from previous phases.
    """

    phase_id: str = "p4"
    timeout_s: float = 1200.0  # 20 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the P4 implementation plan prompt, ported from planning-ralph.sh."""
        output_file = ctx.work_dir / "p4-implementation-plan.md"
        p1_file = ctx.work_dir / "p1-discovery-context.md"
        p2_file = ctx.work_dir / "p2-codebase-analysis.md"
        p3_file = ctx.work_dir / "p3-architecture-design.md"
        planning_date = date.today().isoformat()

        return (
            f"You are conducting Phase P4: Implementation Plan for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Create a detailed, executable implementation plan with file-level and "
            "task-level specificity.\n"
            "Someone should be able to implement this without asking any questions.\n"
            "\n"
            "## Context\n"
            f"- Discovery: {p1_file}\n"
            f"- Codebase: {p2_file}\n"
            f"- Architecture: {p3_file}\n"
            "\n"
            "Read all three files before planning.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"Write to: {output_file}\n"
            "\n"
            "Structure:\n"
            "\n"
            "# P4: Implementation Plan\n"
            f"**Idea**: {ctx.idea_id}\n"
            f"**Date**: {planning_date}\n"
            "**Estimated Effort**: [S/M/L]\n"
            "\n"
            "## Prerequisites\n"
            "Before starting:\n"
            "- [ ] [Prerequisite 1]\n"
            "- [ ] [Prerequisite 2]\n"
            "\n"
            "## Implementation Phases\n"
            "\n"
            "### Phase 1: [Name] (P0 - Critical Path)\n"
            "\n"
            "**Goal**: [What this phase achieves]\n"
            "**Deliverable**: [Concrete output]\n"
            "\n"
            "#### Task 1.1: [Task Name]\n"
            "**File(s)**: `path/to/file.py`\n"
            "**Action**: Create/Modify/Extend\n"
            "**Details**: [pseudocode/structure]\n"
            "**Dependencies**: None / Task X.Y\n"
            "**Verification**: How to test this works\n"
            "\n"
            "### Phase 2: [Name] (P1 - Important)\n"
            "[Same structure...]\n"
            "\n"
            "### Phase 3: [Name] (P2 - Nice to Have)\n"
            "[Same structure...]\n"
            "\n"
            "## File Changes Summary\n"
            "| File | Action | Phase | Lines (est) |\n"
            "|------|--------|-------|-------------|\n"
            "| ... | Create/Modify | ... | ... |\n"
            "\n"
            "## Testing Plan\n"
            "### Unit Tests\n"
            "### Integration Tests\n"
            "### Manual Verification\n"
            "\n"
            "## Rollback Plan\n"
            "## Success Criteria\n"
            "\n"
            "## Blocked Tasks (Need Research)\n"
            "| Task | Blocked By | Research Question |\n"
            "|------|------------|-------------------|\n"
            "| [Task if any] | [Unknown] | [Question for research-ralph] |\n"
            "\n"
            "If this table is empty, proceed directly to implementation.\n"
            "\n"
            "Be extremely specific. Include actual file paths, function names, and code structures."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during P4."""
        return [
            {"name": "Read"},
            {"name": "Write"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> P4Output:
        """Parse P4 output by reading ``p4-implementation-plan.md`` from *work_dir*.

        Extracts phase count and estimated task count from the markdown content.
        Raises :class:`ParseError` if the implementation plan file is missing.
        """
        schedule_file = ctx.work_dir / "p4-implementation-plan.md"

        if not schedule_file.exists():
            raise ParseError(
                f"p4-implementation-plan.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = schedule_file.read_text(encoding="utf-8")

        # Count implementation phases (### Phase N: headings).
        phase_count = len(re.findall(r"###\s+Phase\s+\d+:", content))

        # Count tasks (#### Task N.M: headings).
        estimated_tasks = len(re.findall(r"####\s+Task\s+\d+\.\d+:", content))

        # Fallback: count file changes from the summary table.
        if estimated_tasks == 0:
            file_changes_section = _extract_section(content, "File Changes Summary")
            estimated_tasks = _count_table_rows(file_changes_section)

        return P4Output(
            schedule_file=schedule_file,
            phase_count=phase_count,
            estimated_tasks=estimated_tasks,
        )

    def get_timeout_seconds(self) -> float:
        """Return the P4 timeout in seconds (20 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_section(content: str, heading: str) -> str:
    """Extract content under a markdown ``## heading`` until the next heading."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else ""


def _count_table_rows(section: str) -> int:
    """Count markdown table data rows (excludes header and separator rows)."""
    rows = 0
    for line in section.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip header separator rows like |---|---|---|
        if re.match(r"^\|[\s-]+\|", stripped):
            continue
        # Count lines that look like table rows: | content | ... |
        if stripped.startswith("|") and stripped.endswith("|"):
            rows += 1
    # Subtract 1 for the header row if we counted any rows
    return max(0, rows - 1) if rows > 0 else 0
