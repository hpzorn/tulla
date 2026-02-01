"""Pydantic models and query logic for the ``ralph status`` command."""

from __future__ import annotations

import logging
import os

from pydantic import BaseModel, Field

from ralph.phases.implementation.models import RequirementStatus
from ralph.ports.ontology import OntologyPort

logger = logging.getLogger(__name__)

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
    title: str = Field(default="", description="Short requirement title.")
    status: RequirementStatus = Field(
        default=RequirementStatus.PENDING,
        description="Current status of the requirement.",
    )
    display_status: str = Field(
        default="Pending",
        description="Human-readable status string.",
    )
    deps: list[str] = Field(
        default_factory=list,
        description="Dependency requirement IDs (prd:dependsOn).",
    )


class StatusSummary(BaseModel):
    """Aggregate status with counts across all requirements."""

    rows: list[RequirementRow] = Field(
        default_factory=list,
        description="Individual requirement rows.",
    )
    total: int = Field(default=0, description="Total number of requirements.")
    pending: int = Field(default=0, description="Count of pending requirements.")
    in_progress: int = Field(
        default=0, description="Count of in-progress requirements."
    )
    complete: int = Field(default=0, description="Count of complete requirements.")
    blocked: int = Field(default=0, description="Count of blocked requirements.")
    failed: int = Field(default=0, description="Count of failed requirements.")


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def query_prd_status(
    ontology: OntologyPort,
    prd_context: str,
) -> StatusSummary:
    """Query the ontology for all requirement statuses in a PRD context.

    Uses the batch-fetch approach (ADR-3): one ``recall_facts`` call per
    requirement to retrieve all its properties (status, title, deps) in
    a single round-trip.

    Two-pass classification:
      1. First pass — collect each requirement's raw status and build the
         ``completed_set`` of requirement IDs with status ``prd:Complete``.
      2. Second pass — classify the display status for each requirement,
         detecting ``"Blocked (deps)"`` when a PENDING requirement has
         unmet dependencies.

    Returns a :class:`StatusSummary` with all rows and aggregate counts.
    """
    # Step 1: discover all requirement subjects in the PRD context
    type_facts = ontology.recall_facts(
        predicate="rdf:type",
        context=prd_context,
        limit=500,
    )
    req_subjects = sorted(
        f["subject"]
        for f in type_facts.get("result", [])
        if f.get("object") == "prd:Requirement"
    )

    if not req_subjects:
        logger.info("No requirements found in context %s", prd_context)
        return StatusSummary()

    # Step 2: batch-fetch — one recall_facts per requirement (ADR-3)
    raw: list[dict[str, str | RequirementStatus | list[str]]] = []
    for req_id in req_subjects:
        facts = ontology.recall_facts(
            subject=req_id,
            context=prd_context,
        )
        results = facts.get("result", [])

        title = ""
        status_value = ""
        deps: list[str] = []
        for f in results:
            pred = f.get("predicate", "")
            obj = f.get("object", "")
            if pred == "prd:title":
                title = obj
            elif pred == "prd:status":
                status_value = obj
            elif pred == "prd:dependsOn":
                deps.append(obj)

        # Parse status enum (default to PENDING if missing/unknown)
        try:
            status = RequirementStatus(status_value)
        except ValueError:
            status = RequirementStatus.PENDING

        raw.append({
            "requirement_id": req_id,
            "title": title,
            "status": status,
            "deps": deps,
        })

    # Pass 1: build completed_set
    completed_set: set[str] = {
        str(r["requirement_id"])
        for r in raw
        if r["status"] == RequirementStatus.COMPLETE
    }

    # Pass 2: classify display status and build rows
    rows: list[RequirementRow] = []
    counts: dict[str, int] = {
        "pending": 0,
        "in_progress": 0,
        "complete": 0,
        "blocked": 0,
        "failed": 0,
    }

    for r in raw:
        status: RequirementStatus = r["status"]  # type: ignore[assignment]
        deps: list[str] = r["deps"]  # type: ignore[assignment]

        # Determine display status
        if (
            status == RequirementStatus.PENDING
            and deps
            and not all(d in completed_set for d in deps)
        ):
            display_status = "Blocked (deps)"
            count_key = "blocked"
        else:
            display_status = DISPLAY_STATUS_MAP.get(status, status.value)
            count_key = {
                RequirementStatus.PENDING: "pending",
                RequirementStatus.IN_PROGRESS: "in_progress",
                RequirementStatus.COMPLETE: "complete",
                RequirementStatus.BLOCKED: "blocked",
                RequirementStatus.FAILED: "failed",
            }[status]

        counts[count_key] += 1
        rows.append(RequirementRow(
            requirement_id=str(r["requirement_id"]),
            title=str(r["title"]),
            status=status,
            display_status=display_status,
            deps=deps,
        ))

    return StatusSummary(
        rows=rows,
        total=len(rows),
        **counts,
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _truncate(text: str, width: int) -> str:
    """Truncate *text* to *width*, adding ellipsis if needed."""
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 1:
        return "…"
    return text[: width - 1] + "…"


def format_status_table(
    summary: StatusSummary,
    idea_number: int | None = None,
    *,
    terminal_width: int | None = None,
) -> str:
    """Render *summary* as a Unicode box-drawing table string.

    Parameters
    ----------
    summary:
        The :class:`StatusSummary` to render.
    idea_number:
        Used in the empty-list guard message.
    terminal_width:
        Override terminal width (for testing). Falls back to
        ``os.get_terminal_size().columns`` then 80.
    """
    if not summary.rows:
        n = idea_number if idea_number is not None else "?"
        return f"No requirements found for idea {n}."

    # Determine terminal width
    if terminal_width is None:
        try:
            terminal_width = os.get_terminal_size().columns
        except (ValueError, OSError):
            terminal_width = 80

    # Fixed-width columns
    col_id = "Requirement"
    col_status = "Status"
    col_title = "Title"
    col_deps = "Deps"

    id_width = max(len(col_id), *(len(r.requirement_id) for r in summary.rows))
    status_width = max(
        len(col_status),
        *(len(r.display_status) for r in summary.rows),
    )

    # Separators and padding: "│ " + " │ " * 3 + " │" = 2 + 9 + 2 = 13 chars
    #   outer: 2 (left "│ ") + 2 (right " │") = 4
    #   inner: 3 separators × 3 chars (" │ ") = 9
    chrome = 4 + 3 * 3  # = 13

    remaining = terminal_width - id_width - status_width - chrome
    if remaining < 4:
        # Minimal: at least 2 chars per variable column
        remaining = 4

    title_width = max(len(col_title), int(remaining * 0.6))
    deps_width = max(len(col_deps), remaining - title_width)

    # Ensure we don't exceed terminal width: recalculate if needed
    total = id_width + title_width + status_width + deps_width + chrome
    if total > terminal_width:
        overflow = total - terminal_width
        # Shrink deps first, then title
        deps_shrink = min(overflow, deps_width - len(col_deps))
        if deps_shrink < 0:
            deps_shrink = 0
        deps_width -= deps_shrink
        overflow -= deps_shrink
        if overflow > 0:
            title_width -= overflow

    # Build format helpers
    def fmt_row(req_id: str, title: str, status: str, deps: str) -> str:
        return (
            f"│ {req_id.ljust(id_width)}"
            f" │ {_truncate(title, title_width).ljust(title_width)}"
            f" │ {status.ljust(status_width)}"
            f" │ {_truncate(deps, deps_width).ljust(deps_width)} │"
        )

    # Box-drawing lines
    top = f"┌{'─' * (id_width + 2)}┬{'─' * (title_width + 2)}┬{'─' * (status_width + 2)}┬{'─' * (deps_width + 2)}┐"
    sep = f"├{'─' * (id_width + 2)}┼{'─' * (title_width + 2)}┼{'─' * (status_width + 2)}┼{'─' * (deps_width + 2)}┤"
    bot = f"└{'─' * (id_width + 2)}┴{'─' * (title_width + 2)}┴{'─' * (status_width + 2)}┴{'─' * (deps_width + 2)}┘"

    # Header
    header = fmt_row(col_id, col_title, col_status, col_deps)

    # Data rows
    lines = [top, header, sep]
    for row in summary.rows:
        deps_str = ", ".join(row.deps) if row.deps else ""
        lines.append(fmt_row(row.requirement_id, row.title, row.display_status, deps_str))
    lines.append(bot)

    # Summary line
    lines.append(
        f"Total: {summary.total}"
        f"  Complete: {summary.complete}"
        f"  In Progress: {summary.in_progress}"
        f"  Pending: {summary.pending}"
        f"  Blocked: {summary.blocked}"
        f"  Failed: {summary.failed}"
    )

    return "\n".join(lines)
