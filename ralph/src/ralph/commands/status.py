"""Pydantic models and query logic for the ``ralph status`` command."""

from __future__ import annotations

import logging

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
        ))

    return StatusSummary(
        rows=rows,
        total=len(rows),
        **counts,
    )
