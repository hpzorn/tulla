"""Phase output models for the lightweight pipeline.

# @pattern:MVC -- These BaseModel subclasses are the Model layer, decoupled from phase logic (Controller) and CLI (View)
# @pattern:PortsAndAdapters -- Models define the data contracts exchanged across phase port boundaries
# @principle:SeparationOfConcerns -- IntentField annotations isolated to LightweightTraceResult; other four models use plain Field

Defines five Pydantic ``BaseModel`` subclasses representing each phase's output:

- **IntakeOutput** – change classification and scope
- **ContextScanOutput** – conformance violations and patterns
- **PlanOutput** – planned changes and risk assessment
- **ExecuteOutput** – execution results and commit info
- **LightweightTraceResult** – 9 ``IntentField``-annotated fields for KG persistence

Only ``LightweightTraceResult`` uses ``IntentField``; the other four models use
plain ``pydantic.Field``.

Architecture decisions: arch:adr-53-4, arch:adr-53-3
Quality focus: isaqb:FunctionalCorrectness
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tulla.core.intent import IntentField


# ---------------------------------------------------------------------------
# Phase 1: Intake
# ---------------------------------------------------------------------------

class IntakeOutput(BaseModel):
    """Output of the Intake phase – change classification and scope."""

    change_type: str = Field(
        description=(
            "One of the 6-category taxonomy: "
            "bugfix, feature, enhancement, chore, test, refactor"
        ),
    )
    description: str = Field(description="Human-readable change description")
    affected_files: list[str] = Field(
        description="Files affected by this change",
    )
    scope: str = Field(
        description="Package scope: 'single-package' or 'cross-package'",
    )
    lightweight_eligible: bool = Field(
        description="Whether this change qualifies for the lightweight pipeline",
    )


# ---------------------------------------------------------------------------
# Phase 2: Context Scan
# ---------------------------------------------------------------------------

class ContextScanOutput(BaseModel):
    """Output of the Context Scan phase – conformance violations and patterns."""

    violations: list[dict] = Field(
        default_factory=list,
        description="List of conformance violation records",
    )
    violation_report: str = Field(
        default="",
        description="Human-readable violation report",
    )
    patterns: list[str] = Field(
        default_factory=list,
        description="Detected code patterns",
    )
    principles: list[str] = Field(
        default_factory=list,
        description="Applicable design principles",
    )
    conformance_status: str = Field(
        description="Conformance status in format 'structural-only:{status}'",
    )
    quality_focus: str = Field(
        default="",
        description="Quality attribute focus area",
    )


# ---------------------------------------------------------------------------
# Phase 3: Plan
# ---------------------------------------------------------------------------

class PlanOutput(BaseModel):
    """Output of the Plan phase – planned changes and risk assessment."""

    plan_summary: str = Field(description="Summary of the implementation plan")
    plan_steps: list[str] = Field(description="Ordered list of plan steps")
    files_to_modify: list[str] = Field(description="Files that will be modified")
    risk_notes: str = Field(default="", description="Risk assessment notes")


# ---------------------------------------------------------------------------
# Phase 4: Execute
# ---------------------------------------------------------------------------

class ExecuteOutput(BaseModel):
    """Output of the Execute phase – execution results and commit info."""

    changes_summary: str = Field(description="Summary of changes made")
    files_modified: list[str] = Field(description="Files that were modified")
    commit_ref: str = Field(description="Git commit reference")
    execution_notes: str = Field(
        default="",
        description="Additional execution notes",
    )


# ---------------------------------------------------------------------------
# Phase 5: Lightweight Trace (KG persistence)
# ---------------------------------------------------------------------------

class LightweightTraceResult(BaseModel):
    """Trace output with 9 IntentField-annotated fields for KG persistence.

    Six required fields and three optional fields (default ``None``).
    ``extract_intent_fields()`` returns only non-None intent fields:
    6 keys when optionals are absent, 9 keys when all are populated.

    Architecture decision: arch:adr-53-4
    """

    # --- 6 required fields ---------------------------------------------------

    change_type: str = IntentField(
        description=(
            "One of the 6-category taxonomy: "
            "bugfix, feature, enhancement, chore, test, refactor"
        ),
    )
    affected_files: str = IntentField(
        description="Comma-separated list of affected files",
    )
    conformance_assertion: str = IntentField(
        description="Conformance assertion from context scan",
    )
    commit_ref: str = IntentField(
        description="Git commit reference",
    )
    change_summary: str = IntentField(
        description="Summary of the change",
    )
    timestamp: str = IntentField(
        description="ISO 8601 timestamp",
    )

    # --- 3 optional fields (default=None) ------------------------------------

    issue_ref: str | None = IntentField(
        default=None,
        description="Issue tracker reference",
    )
    sprint_id: str | None = IntentField(
        default=None,
        description="Sprint identifier",
    )
    story_points: str | None = IntentField(
        default=None,
        description="Story point estimate",
    )
