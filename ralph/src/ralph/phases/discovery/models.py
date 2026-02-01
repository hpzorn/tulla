"""Pydantic data models for the Discovery phase (D1–D5)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class DiscoveryInput(BaseModel):
    """Input parameters for a discovery phase run."""

    idea_id: str
    work_dir: Path
    idea_title: str
    idea_description: str


class D1Output(BaseModel):
    """Output of D1 – Tool & MCP Inventory."""

    inventory_file: Path
    tools_found: int
    mcp_servers_found: int


class D2Output(BaseModel):
    """Output of D2 – Persona Generation."""

    personas_file: Path
    persona_count: int


class D3Output(BaseModel):
    """Output of D3 – Value Mapping."""

    value_mapping_file: Path
    total_value_score: int
    quadrant: str


class D4Output(BaseModel):
    """Output of D4 – Gap Analysis."""

    gap_analysis_file: Path
    gaps_found: int
    p0_gaps: int


class D5Output(BaseModel):
    """Output of D5 – Discovery Summary & Recommendation."""

    output_file: Path
    mode: str
    recommendation: str
