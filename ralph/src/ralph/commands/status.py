"""Pydantic models for the ``ralph status`` command."""

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
