"""Pydantic models and query logic for the ``ralph status`` command.

RequirementRow holds display data for a single requirement.
StatusSummary aggregates counts across all requirements.
DISPLAY_STATUS_MAP translates RequirementStatus enum values to human-readable strings.
query_prd_status() queries the ontology and returns a fully populated StatusSummary.
"""

from __future__ import annotations

import logging

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
