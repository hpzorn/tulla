"""Pydantic data models for the Discovery phase (D1–D5).

# @pattern:PipesAndFilters -- D1-D5 outputs form a typed pipeline; each phase consumes the previous output and produces a new DxOutput that feeds downstream phases
# @pattern:Plugin -- Each DxOutput is a self-describing plugin; adding IntentField annotations registers new facts without modifying core persistence code
# @pattern:Blackboard -- IntentField-annotated fields on each DxOutput constitute a shared fact blackboard; PhaseFactPersister and extract_intent_fields read/write these slots independently
# @principle:SeparationOfConcerns -- Plain Path fields carry artefact locations while IntentField-annotated fields carry decision metrics; persistence reads only the intent subset
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
    tools_found: int = IntentField(description="Number of tools discovered")
    mcp_servers_found: int = IntentField(description="Number of MCP servers discovered")


class D2Output(BaseModel):
    """Output of D2 – Persona Generation."""

    personas_file: Path
    persona_count: int = IntentField(description="Number of personas generated")


class D3Output(BaseModel):
    """Output of D3 – Value Mapping."""

    value_mapping_file: Path
    total_value_score: int = IntentField(description="Total value score (0-60)")
    quadrant: str = IntentField(description="Value-effort quadrant classification")


class D4Output(BaseModel):
    """Output of D4 – Gap Analysis."""

    gap_analysis_file: Path
    gaps_found: int
    p0_gaps: int


class D5Output(BaseModel):
    """Output of D5 – Discovery Summary & Recommendation."""

    output_file: Path
    mode: str = IntentField(description="Selected pipeline mode (research/plan/implement)")
    recommendation: str = IntentField(description="Discovery recommendation for next steps")
