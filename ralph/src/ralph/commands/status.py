"""Pydantic models for the ``ralph status`` command display layer.

RequirementRow holds display data for a single requirement.
StatusSummary aggregates counts across all requirements.
DISPLAY_STATUS_MAP translates RequirementStatus enum values to human-readable strings.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ralph.phases.implementation.models import RequirementStatus


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
