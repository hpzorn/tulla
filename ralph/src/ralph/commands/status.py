"""Pydantic models and query logic for the ``ralph status`` command.

RequirementRow holds display data for a single requirement.
StatusSummary aggregates counts across all requirements.
DISPLAY_STATUS_MAP translates RequirementStatus enum values to human-readable strings.
query_prd_status() queries the ontology and returns a fully populated StatusSummary.
"""

from __future__ import annotations

import logging
import os

from pydantic import BaseModel, Field

from ralph.phases.implementation.models import RequirementStatus
from ralph.ports.ontology import OntologyPort

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUS_VALUE_MAP: dict[str, RequirementStatus] = {
    s.value: s for s in RequirementStatus
}


# ---------------------------------------------------------------------------
# Display mapping
# ---------------------------------------------------------------------------

DISPLAY_STATUS_MAP: dict[RequirementStatus, str] = {
    RequirementStatus.PENDING: "Pending",
    RequirementStatus.IN_PROGRESS: "In Progress",
    RequirementStatus.COMPLETE: "Complete",
    RequirementStatus.BLOCKED: "Blocked",
    RequirementStatus.FAILED: "Failed",
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RequirementRow(BaseModel):
    """Display data for a single requirement."""

    requirement_id: str = Field(description="The prd:req-* identifier.")
    title: str = Field(default="", description="Short human-readable title.")
    status: RequirementStatus = Field(
        default=RequirementStatus.PENDING,
        description="Current status from the ontology.",
    )
    display_status: str = Field(
        default="Pending",
        description="Human-readable status string.",
    )


class StatusSummary(BaseModel):
    """Aggregate status counts across all requirements."""

    total: int = Field(default=0, description="Total number of requirements.")
    pending: int = Field(default=0, description="Count with status Pending.")
    in_progress: int = Field(default=0, description="Count with status In Progress.")
    complete: int = Field(default=0, description="Count with status Complete.")
    blocked: int = Field(default=0, description="Count with status Blocked.")
    failed: int = Field(default=0, description="Count with status Failed.")
    rows: list[RequirementRow] = Field(
        default_factory=list,
        description="Per-requirement display rows.",
    )


# ---------------------------------------------------------------------------
# Query function
# ---------------------------------------------------------------------------


def query_prd_status(
    ontology: OntologyPort,
    prd_context: str,
) -> StatusSummary:
    """Query the ontology for all requirement statuses and return a summary.

    Uses the batch-fetch approach (ADR-3): one ``recall_facts`` call per
    requirement to retrieve its status. A two-pass classification builds
    the display rows:

    - **Pass 1** collects raw statuses and titles, builds the
      ``completed_set`` of requirement IDs with status ``prd:Complete``.
    - **Pass 2** classifies each requirement's display status, detecting
      ``"Blocked (deps)"`` for pending requirements whose dependencies
      are not all complete.

    Parameters:
        ontology: Ontology port for querying facts.
        prd_context: The ontology context holding PRD facts
            (e.g. ``"prd-idea-54"``).

    Returns:
        A :class:`StatusSummary` with per-requirement rows and aggregate
        counts.
    """
    # 0. Discover all requirements in this PRD context
    all_facts = ontology.recall_facts(
        predicate="rdf:type",
        context=prd_context,
        limit=500,
    )
    results = all_facts.get("result", [])
    req_ids = sorted(
        f["subject"]
        for f in results
        if f.get("object") == "prd:Requirement"
    )

    if not req_ids:
        logger.info("No requirements found in context %s", prd_context)
        return StatusSummary()

    # ------------------------------------------------------------------
    # Pass 1: Collect statuses and titles, build completed_set
    # ------------------------------------------------------------------
    status_map: dict[str, RequirementStatus] = {}
    title_map: dict[str, str] = {}
    completed_set: set[str] = set()

    for req_id in req_ids:
        # Fetch status (one recall_facts per requirement — ADR-3)
        status_facts = ontology.recall_facts(
            subject=req_id,
            predicate="prd:status",
            context=prd_context,
        )
        status_results = status_facts.get("result", [])
        if status_results:
            raw_status = status_results[0].get("object", "")
            req_status = _STATUS_VALUE_MAP.get(
                raw_status, RequirementStatus.PENDING
            )
        else:
            req_status = RequirementStatus.PENDING

        status_map[req_id] = req_status
        if req_status == RequirementStatus.COMPLETE:
            completed_set.add(req_id)

        # Fetch title
        title_facts = ontology.recall_facts(
            subject=req_id,
            predicate="prd:title",
            context=prd_context,
        )
        title_results = title_facts.get("result", [])
        title_map[req_id] = (
            title_results[0].get("object", "") if title_results else ""
        )

    # ------------------------------------------------------------------
    # Pass 2: Classify display status (including "Blocked (deps)")
    # ------------------------------------------------------------------
    rows: list[RequirementRow] = []

    for req_id in req_ids:
        req_status = status_map[req_id]
        display = DISPLAY_STATUS_MAP.get(req_status, "Pending")

        # Detect blocked-by-dependencies: pending reqs with unsatisfied deps
        if req_status == RequirementStatus.PENDING:
            dep_facts = ontology.recall_facts(
                subject=req_id,
                predicate="prd:dependsOn",
                context=prd_context,
            )
            dep_results = dep_facts.get("result", [])
            deps = [d.get("object", "") for d in dep_results]
            if deps and not all(d in completed_set for d in deps):
                display = "Blocked (deps)"

        rows.append(
            RequirementRow(
                requirement_id=req_id,
                title=title_map.get(req_id, ""),
                status=req_status,
                display_status=display,
            )
        )

    # ------------------------------------------------------------------
    # Aggregate counts
    # ------------------------------------------------------------------
    counts: dict[str, int] = {
        "pending": 0,
        "in_progress": 0,
        "complete": 0,
        "blocked": 0,
        "failed": 0,
    }
    status_to_count_key: dict[RequirementStatus, str] = {
        RequirementStatus.PENDING: "pending",
        RequirementStatus.IN_PROGRESS: "in_progress",
        RequirementStatus.COMPLETE: "complete",
        RequirementStatus.BLOCKED: "blocked",
        RequirementStatus.FAILED: "failed",
    }
    for row in rows:
        key = status_to_count_key.get(row.status, "pending")
        counts[key] += 1

    return StatusSummary(
        total=len(rows),
        rows=rows,
        **counts,
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

# Unicode box-drawing characters
_H = "\u2500"  # ─
_V = "\u2502"  # │
_TL = "\u250c"  # ┌
_TR = "\u2510"  # ┐
_BL = "\u2514"  # └
_BR = "\u2518"  # ┘
_TM = "\u252c"  # ┬
_BM = "\u2534"  # ┴
_LM = "\u251c"  # ├
_RM = "\u2524"  # ┤
_CM = "\u253c"  # ┼


def _terminal_width() -> int:
    """Return terminal width with fallback of 80."""
    try:
        return os.get_terminal_size().columns
    except (ValueError, OSError):
        return 80


def _truncate(text: str, width: int) -> str:
    """Truncate *text* to *width*, appending '…' if needed."""
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return "\u2026"
    return text[: width - 1] + "\u2026"


def format_status_table(summary: StatusSummary, idea_id: int | None = None) -> str:
    """Render a *StatusSummary* as a Unicode box-drawing table string.

    Columns: ``ID | Title | Status | Deps``

    The table adapts to the current terminal width (fallback 80).  Fixed-width
    columns (ID, Status) are sized to their content.  The remaining width is
    split proportionally: **Title 60 %**, **Deps 40 %**.  Values exceeding
    their column width are truncated with ``…``.

    Parameters:
        summary: The :class:`StatusSummary` to render.
        idea_id: Optional idea number shown in the empty-list guard message.

    Returns:
        A multi-line string containing the rendered table, or a short message
        when *summary* contains no rows.
    """
    # Empty-list guard
    if not summary.rows:
        label = f" for idea {idea_id}" if idea_id is not None else ""
        return f"No requirements found{label}."

    # -- Collect per-row cell values -----------------------------------------
    id_cells: list[str] = []
    title_cells: list[str] = []
    status_cells: list[str] = []
    deps_cells: list[str] = []

    for row in summary.rows:
        id_cells.append(row.requirement_id)
        title_cells.append(row.title)
        status_cells.append(row.display_status)
        # Deps column: show "Blocked (deps)" indicator or empty
        deps_cells.append("yes" if row.display_status == "Blocked (deps)" else "")

    # -- Column headers ------------------------------------------------------
    hdr_id = "ID"
    hdr_title = "Title"
    hdr_status = "Status"
    hdr_deps = "Deps"

    # -- Fixed-width columns: sized to content (including header) ------------
    id_width = max(len(hdr_id), *(len(c) for c in id_cells))
    status_width = max(len(hdr_status), *(len(c) for c in status_cells))

    # -- Variable-width columns: share remaining space -----------------------
    term_w = _terminal_width()
    # 5 separators (│ at each boundary): │ID│Title│Status│Deps│
    # Each separator takes 3 chars: " │ " (space-pipe-space) except outer │
    # Layout:  │ ID │ Title │ Status │ Deps │
    #          1    +padding*4 columns + 5 pipes = overhead
    # Overhead: 5 pipes + 8 spaces (2 per column padding) = 13
    overhead = 5 + 2 * 4  # 5 │ chars + 2 spaces per 4 columns
    remaining = term_w - overhead - id_width - status_width
    remaining = max(remaining, 8)  # absolute minimum for variable cols

    title_width = max(len(hdr_title), int(remaining * 0.6))
    deps_width = max(len(hdr_deps), remaining - title_width)

    # -- Helper to build one row of cells ------------------------------------
    def _row(id_v: str, title_v: str, status_v: str, deps_v: str) -> str:
        return (
            f"{_V} {_truncate(id_v, id_width).ljust(id_width)} "
            f"{_V} {_truncate(title_v, title_width).ljust(title_width)} "
            f"{_V} {_truncate(status_v, status_width).ljust(status_width)} "
            f"{_V} {_truncate(deps_v, deps_width).ljust(deps_width)} {_V}"
        )

    # -- Horizontal lines ----------------------------------------------------
    def _hline(left: str, mid: str, right: str) -> str:
        return (
            f"{left}{_H * (id_width + 2)}"
            f"{mid}{_H * (title_width + 2)}"
            f"{mid}{_H * (status_width + 2)}"
            f"{mid}{_H * (deps_width + 2)}{right}"
        )

    top = _hline(_TL, _TM, _TR)
    sep = _hline(_LM, _CM, _RM)
    bot = _hline(_BL, _BM, _BR)

    # -- Assemble table ------------------------------------------------------
    lines: list[str] = [top]
    lines.append(_row(hdr_id, hdr_title, hdr_status, hdr_deps))
    lines.append(sep)
    for id_v, title_v, status_v, deps_v in zip(
        id_cells, title_cells, status_cells, deps_cells
    ):
        lines.append(_row(id_v, title_v, status_v, deps_v))
    lines.append(bot)

    # -- Summary line --------------------------------------------------------
    parts: list[str] = [f"Total: {summary.total}"]
    if summary.complete:
        parts.append(f"Complete: {summary.complete}")
    if summary.in_progress:
        parts.append(f"In Progress: {summary.in_progress}")
    if summary.pending:
        parts.append(f"Pending: {summary.pending}")
    if summary.blocked:
        parts.append(f"Blocked: {summary.blocked}")
    if summary.failed:
        parts.append(f"Failed: {summary.failed}")
    lines.append(" | ".join(parts))

    return "\n".join(lines)
