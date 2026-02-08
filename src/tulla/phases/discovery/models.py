"""Pydantic data models for the Discovery phase (D1–D5).

# @pattern:PipesAndFilters -- D1-D5 outputs form a typed pipeline; each phase consumes the previous DxOutput and produces a new one that feeds downstream phases
# @pattern:Plugin -- Each DxOutput is a self-describing plugin; adding IntentField annotations registers new facts without modifying core persistence code
# @pattern:Blackboard -- IntentField-annotated fields on each DxOutput constitute a shared fact blackboard; PhaseFactPersister and extract_intent_fields read/write these slots independently
# @principle:SingleResponsibility -- Each DxOutput model owns exactly one phase's output schema; D4Output holds only gap-analysis results, not summary or value data
# @principle:SeparationOfConcerns -- Plain Path fields carry artefact locations while IntentField-annotated fields carry decision metrics; persistence reads only the intent subset
# @principle:DependencyInversion -- DxOutput models depend on the abstract IntentField marker, not on concrete PhaseFactPersister; persistence discovers fields at runtime via extract_intent_fields
# @principle:OpenClosedPrinciple -- New intent fields extend phase outputs via IntentField annotation only; extract_intent_fields discovers them without core code changes
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from tulla.core.intent import IntentField


class DiscoveryInput(BaseModel):
    """Input parameters for a discovery phase run."""

    idea_id: str
    work_dir: Path
    idea_title: str
    idea_description: str


class D1Output(BaseModel):
    """Output of D1 – Tool & MCP Inventory."""

    inventory_file: Path
    key_capabilities: str = IntentField(
        default="[]",
        description="JSON list of {name, location, relevance} for reusable components",
    )
    ecosystem_context: str = IntentField(
        default="",
        description="How this idea fits into the broader system",
    )
    reuse_opportunities: str = IntentField(
        default="",
        description="What's already built that this idea can leverage (from Prior Work)",
    )


class D2Output(BaseModel):
    """Output of D2 – Persona Generation."""

    personas_file: Path
    personas: str = IntentField(
        default="[]",
        description="JSON list of {name, role, primary_jtbd} per persona",
    )
    non_negotiable_needs: str = IntentField(
        default="[]",
        description="JSON list of non-negotiable user needs from cross-persona analysis",
    )
    primary_persona_jtbd: str = IntentField(
        default="",
        description="Synthesized JTBD statement: When I [situation], I want [motivation], so I can [outcome]",
    )


class D3Output(BaseModel):
    """Output of D3 – Value Mapping."""

    value_mapping_file: Path
    quadrant: str = IntentField(description="Value-effort quadrant classification")
    strategic_constraints: str = IntentField(
        default="[]",
        description="JSON list of constraints, dependencies, and risks",
    )
    verdict: str = IntentField(
        default="",
        description="Compact strategic statement: priority + ROI verdict + confidence",
    )


class D4Output(BaseModel):
    """Output of D4 – Gap Analysis."""

    gap_analysis_file: Path
    blockers: str = IntentField(
        default="",
        description="Critical path narrative of blocking gaps that must resolve first",
    )
    root_blocker: str = IntentField(
        default="",
        description="The single gap everything else depends on — first priority item",
    )
    recommended_next_steps: str = IntentField(
        default="",
        description="Recommended next steps from gap analysis",
    )


class D5Output(BaseModel):
    """Output of D5 – Discovery Summary & Recommendation."""

    output_file: Path
    mode: str = IntentField(description="Selected pipeline mode (research/plan/implement)")
    recommendation: str = IntentField(description="Discovery recommendation for next steps")
    northstar: str = IntentField(
        default="",
        description="Compact idea definition: what it is, for whom, what success looks like",
    )
    mandatory_features: str = IntentField(
        default="[]",
        description="JSON list of must-have features/requirements that must survive into planning",
    )
    key_constraints: str = IntentField(
        default="[]",
        description="JSON list of constraints from all prior phases",
    )
