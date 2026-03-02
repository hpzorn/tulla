"""P4 Phase – Implementation Plan.

Implements the fourth planning sub-phase that creates a detailed,
executable implementation plan with file-level and task-level specificity.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any

import click

from tulla.core.phase import ParseError, Phase, PhaseContext
from tulla.core.phase_facts import group_upstream_facts
from tulla.phases.planning import PLANNING_IDENTITY, build_northstar_section

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
        """Build the P4 implementation plan prompt, ported from planning-tulla.sh."""
        output_file = ctx.work_dir / "p4-implementation-plan.md"
        p1_file = ctx.work_dir / "p1-discovery-context.md"
        p2_file = ctx.work_dir / "p2-codebase-analysis.md"
        p3_file = ctx.work_dir / "p3-architecture-design.md"
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
            + f"## Phase P4: Implementation Plan\n"
            f"**Idea**: {ctx.idea_id}\n"
            "\n"
            f"{northstar_section}"
            f"{upstream_section}"
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
            "**CRITICAL**: Your implementation plan MUST have tasks "
            "for ALL features from P1's Feature Scope.\n"
            "Cross-reference with P3's Feature Coverage Matrix. "
            "Every feature gets implementation tasks.\n"
            "Do not drop features. Do not add features not in the scope.\n"
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
            "**Details**: [2-4 sentence prose description of WHAT to build, not HOW]\n"
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
            "## Feature Coverage Checklist (REQUIRED)\n"
            "\n"
            "Verify ALL features from P1 have implementation tasks:\n"
            "\n"
            "| Feature (from P1) | Implemented in Phase | Tasks | Status |\n"
            "|-------------------|---------------------|-------|--------|\n"
            "| [Feature 1] | Phase N | Task N.1, N.2 | ✓ Covered |\n"
            "| [Feature 2] | Phase M | Task M.1 | ✓ Covered |\n"
            "| ... | ... | ... | ... |\n"
            "\n"
            "**Coverage**: [X]/[Y] features have tasks. "
            "If any feature shows '✗ Missing', add tasks.\n"
            "\n"
            "## Blocked Tasks (Need Research)\n"
            "| Task | Blocked By | Research Question |\n"
            "|------|------------|-------------------|\n"
            "| [Task if any] | [Unknown] | [Question for research-tulla] |\n"
            "\n"
            "If this table is empty, proceed directly to implementation.\n"
            "\n"
            "Be specific about file paths, function/class names, and interfaces.\n"
            "\n"
            "IMPORTANT constraints on task Details:\n"
            "- Describe WHAT to build in 2-4 sentences of prose, not HOW to build it.\n"
            "- Do NOT include code blocks, pseudocode, or inline code snippets.\n"
            "- Do NOT write implementation code — that is Implementation-Tulla's job.\n"
            "- Focus on: inputs, outputs, interfaces, data structures, and acceptance criteria.\n"
            "- Bad: ```python\\ndef foo(): ...```\n"
            "- Good: \"Create function `foo()` that accepts a list "
            "of Requirement objects and returns a dependency DAG "
            "as a dict mapping task IDs to their transitive "
            "dependencies.\"\n"
            "\n"
            "### EXCEPTION: Prompt-Content Tasks\n"
            "\n"
            "When a task involves creating or modifying an AI prompt (a `build_prompt()` method,\n"
            "agent instructions, or phase prompt template), the Details section MUST be expanded\n"
            "beyond 2-4 sentences to specify the DOMAIN METHODOLOGY the prompt should encode:\n"
            "\n"
            "- List the specific **methodological steps** the "
            "prompt must instruct the AI to follow\n"
            "- Name the **frameworks, taxonomies, or protocols** the prompt must reference\n"
            "  (e.g., PICOS, GRADE, systematic review checklist, experimental design types)\n"
            "- Specify the **quality criteria** the prompt must enforce for output quality\n"
            "- Describe the **failure modes** the prompt must guard against\n"
            "- Include **concrete examples** of good vs bad outputs where helpful\n"
            "\n"
            "This is NOT implementation code — it is specification of the intellectual content\n"
            "that the prompt must encode. The prompt IS the product for AI-driven phases.\n"
            "\n"
            "Bad: 'Update R4 prompt with mode preamble for groundwork vs spike'\n"
            "Good: 'Update R4 Literature Review prompt to instruct: (1) systematic search using\n"
            "constructed keyword queries across official docs, repositories, and papers,\n"
            "(2) source credibility assessment using recency, peer-review status, and citation\n"
            "authority, (3) thematic synthesis across sources identifying patterns and\n"
            "contradictions, (4) evidence grading as strong/moderate/weak with explicit\n"
            "criteria, (5) comparison matrix mapping approaches to quality attributes,\n"
            "(6) explicit anti-pattern documentation with rationale for why each fails'"
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

        # -- Per-task granularity extraction --
        max_files = int(ctx.config.get("max_files_per_requirement", 3))
        min_wpf = float(ctx.config.get("min_wpf_blocking", 12.0))

        coarse_tasks: list[dict[str, Any]] = []
        for task_match in re.finditer(
            r"####\s+Task\s+(\d+\.\d+):\s*(.+?)(?=\n####\s+Task|\n###\s+Phase|\n##\s|\Z)",
            content,
            re.DOTALL,
        ):
            task_id = task_match.group(1)
            task_body = task_match.group(2)

            files = _extract_task_files(task_body)
            details = _extract_task_details(task_body)

            file_count = len(files)
            word_count = len(details.split()) if details else 0
            wpf = word_count / file_count if file_count > 0 else 0.0
            homogeneous = _check_homogeneity(files)

            if file_count > max_files and not homogeneous and wpf < min_wpf:
                coarse_tasks.append({
                    "task": task_id,
                    "file_count": file_count,
                    "word_count": word_count,
                    "wpf": round(wpf, 2),
                    "homogeneous": homogeneous,
                })

        granularity_passed = len(coarse_tasks) == 0

        return P4Output(
            schedule_file=schedule_file,
            phase_count=phase_count,
            estimated_tasks=estimated_tasks,
            coarse_tasks=coarse_tasks,
            granularity_passed=granularity_passed,
        )

    def validate_output(self, ctx: PhaseContext, parsed: P4Output) -> None:
        """Log advisory warnings for coarse tasks but never raise.

        Per ADR-64-2 this gate is advisory only: it emits a warning per
        coarse task via ``ctx.logger.warning`` and ``click.echo`` to
        stderr, but does **not** raise ``ValueError`` so execution
        always continues.
        """
        for entry in parsed.coarse_tasks:
            msg = (
                f"P4 advisory: Task {entry['task']} appears coarse "
                f"(files={entry['file_count']}, wpf={entry['wpf']})"
            )
            ctx.logger.warning(msg)
            click.echo(msg, err=True)

    def get_timeout_seconds(self) -> float:
        """Return the P4 timeout in seconds (20 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _check_homogeneity(files: list[str]) -> bool:
    """Return True if all files match a single glob pattern.

    Files are homogeneous when they share the same basename
    (e.g. all ``__init__.py``) or the same extension (e.g. all ``.py``).
    This exempts bootstrap requirements from the file-count blocking threshold.
    """
    if len(files) <= 1:
        return True

    basenames = {os.path.basename(f) for f in files}
    if len(basenames) == 1:
        return True

    extensions = {os.path.splitext(f)[1] for f in files}
    return bool(len(extensions) == 1 and extensions != {""})


def _extract_task_files(task_body: str) -> list[str]:
    """Extract file paths from a ``**File(s)**: ...`` line inside a task block."""
    match = re.search(r"\*\*File\(s\)\*\*:\s*(.+)", task_body)
    if not match:
        return []
    raw = match.group(1).strip()
    # Strip backticks and split on commas or whitespace-separated entries.
    raw = raw.replace("`", "")
    parts = [p.strip() for p in re.split(r"[,\s]+", raw) if p.strip()]
    return parts


def _extract_task_details(task_body: str) -> str:
    """Extract the Details text from a ``**Details**: ...`` line inside a task block."""
    match = re.search(
        r"\*\*Details\*\*:\s*(.+?)(?=\n\*\*[A-Z]|\Z)", task_body, re.DOTALL
    )
    return match.group(1).strip() if match else ""


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
