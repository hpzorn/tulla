"""Pydantic data models for the Implementation phase (loop-based architecture).

Unlike the linear pipeline phases (Discovery, Planning, Research), the
Implementation phase uses a Find-Implement-Commit-Verify-Status loop.
These models represent the inputs and outputs of each loop step.

# @pattern:PipesAndFilters -- Find→Implement→Commit→Verify→Status outputs chain through the loop; each step model feeds the next via IterationResult
# @pattern:Plugin -- IterationFactRecord is a self-describing plugin; adding IntentField annotations registers new facts without modifying PhaseFactPersister
# @pattern:Blackboard -- IterationFactRecord fields form a shared fact blackboard persisted after Status; downstream phases read these slots via extract_intent_fields
# @principle:SingleResponsibility -- Each step model (FindOutput, CommitOutput, etc.) owns exactly one step's schema; IterationFactRecord owns only the persisted fact subset
# @principle:SeparationOfConcerns -- Step-level models carry operational fields (cost_usd, duration_s) while IterationFactRecord carries only intent-preserving decision fields
# @principle:OpenClosedPrinciple -- New iteration facts extend IterationFactRecord via IntentField annotation; extract_intent_fields discovers them without core code changes
# @principle:DependencyInversion -- Models depend on the abstract IntentField marker, not on concrete PhaseFactPersister; persistence discovers fields at runtime via extract_intent_fields
"""

from __future__ import annotations

import enum
from pathlib import Path

from pydantic import BaseModel, Field

from tulla.core.intent import IntentField


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RequirementStatus(str, enum.Enum):
    """Status of a requirement in the ontology."""

    PENDING = "prd:Pending"
    IN_PROGRESS = "prd:InProgress"
    COMPLETE = "prd:Complete"
    BLOCKED = "prd:Blocked"
    FAILED = "prd:Failed"


class LoopOutcome(str, enum.Enum):
    """Outcome of a single iteration of the implementation loop."""

    IMPLEMENTED = "IMPLEMENTED"
    VERIFY_FAILED = "VERIFY_FAILED"
    ALL_COMPLETE = "ALL_COMPLETE"
    ERROR = "ERROR"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


# ---------------------------------------------------------------------------
# Step outputs
# ---------------------------------------------------------------------------


class FindOutput(BaseModel):
    """Output of the FindPhase — identifies the next requirement to implement."""

    requirement_id: str | None = Field(
        default=None,
        description="The prd:req-* identifier, or None if all requirements are done.",
    )
    title: str = ""
    description: str = ""
    files: list[str] = Field(default_factory=list)
    action: str = ""
    verification: str = ""
    all_complete: bool = False
    related_adrs: list[str] = Field(
        default_factory=list,
        description="ADR identifiers linked to this requirement via prd:relatedADR.",
    )
    quality_focus: str = Field(
        default="",
        description="Quality attribute focus for this requirement (prd:qualityFocus).",
    )
    resolved_patterns: list[str] = Field(
        default_factory=list,
        description="Patterns resolved from quality_focus via SPARQL.",
    )
    resolved_principles: list[str] = Field(
        default_factory=list,
        description="Principles resolved from quality_focus via SPARQL.",
    )
    resolved_design_patterns: list[str] = Field(
        default_factory=list,
        description="Design patterns resolved from quality_focus via SPARQL.",
    )


class ImplementOutput(BaseModel):
    """Output of the ImplementPhase — Claude code generation result."""

    requirement_id: str
    files_changed: list[str] = Field(default_factory=list)
    output_text: str = ""
    cost_usd: float = 0.0
    duration_s: float = 0.0


class CommitOutput(BaseModel):
    """Output of the CommitPhase — git commit result."""

    requirement_id: str
    commit_hash: str = ""
    committed: bool = False
    message: str = ""


class VerifyOutput(BaseModel):
    """Output of the VerifyPhase — Claude verification against spec."""

    requirement_id: str
    passed: bool = False
    feedback: str = ""
    cost_usd: float = 0.0
    duration_s: float = 0.0


class StatusOutput(BaseModel):
    """Output of the StatusPhase — ontology status update."""

    requirement_id: str
    new_status: RequirementStatus
    updated: bool = False


# ---------------------------------------------------------------------------
# Loop-level models
# ---------------------------------------------------------------------------


class IterationResult(BaseModel):
    """Result of a single loop iteration (Find→Implement→Commit→Verify→Status)."""

    requirement_id: str | None = None
    outcome: LoopOutcome
    find: FindOutput | None = None
    implement: ImplementOutput | None = None
    commit: CommitOutput | None = None
    verify: VerifyOutput | None = None
    status: StatusOutput | None = None
    retries_used: int = 0
    error: str | None = None


class LoopResult(BaseModel):
    """Aggregate result of the full implementation loop."""

    iterations: list[IterationResult] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    requirements_completed: int = 0
    requirements_blocked: int = 0
    all_complete: bool = False


# ---------------------------------------------------------------------------
# Iteration fact record (persisted after Status step)
# ---------------------------------------------------------------------------


class IterationFactRecord(BaseModel):
    """Intent-carrying output of a single implementation iteration.

    Persisted after the Status step of each loop iteration.  All five
    fields carry the IntentField marker so that PhaseFactPersister and
    extract_intent_fields can discover and persist them as A-Box triples.
    """

    requirement_id: str = IntentField(
        description="The prd:req-* identifier implemented in this iteration",
    )
    quality_focus: str = IntentField(
        description="iSAQB quality attribute targeted by this requirement",
    )
    passed: bool = IntentField(
        description="Whether the verification step passed",
    )
    feedback: str = IntentField(
        description="Verification feedback or failure reason",
    )
    commit_hash: str = IntentField(
        description="Git commit hash produced by the commit step",
    )
