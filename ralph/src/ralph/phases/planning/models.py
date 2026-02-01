"""Pydantic data models for the Planning phase (P1–P6)."""

from __future__ import annotations

from dataclasses import dataclass as _dc_dataclass
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from ralph.hygiene.preflight import HygieneReport


class PlanningInput(BaseModel):
    """Input parameters for a planning phase run."""

    idea_id: str
    work_dir: Path
    idea_title: str
    idea_description: str
    discovery_output_dir: Path


class P1Input(BaseModel):
    """Input for P1 – Ontology Query & Context Assembly."""

    idea_id: str
    work_dir: Path


class P1Output(BaseModel):
    """Output of P1 – Ontology Query & Context Assembly."""

    context_file: Path
    triples_loaded: int
    ontologies_queried: list[str]


class P2Input(BaseModel):
    """Input for P2 – Requirement Decomposition."""

    idea_id: str
    work_dir: Path
    context_file: Path


class P2Output(BaseModel):
    """Output of P2 – Requirement Decomposition."""

    requirements_file: Path
    requirement_count: int
    p0_count: int


class P3Input(BaseModel):
    """Input for P3 – Dependency Analysis."""

    idea_id: str
    work_dir: Path
    requirements_file: Path


class P3Output(BaseModel):
    """Output of P3 – Dependency Analysis."""

    dependency_graph_file: Path
    total_dependencies: int
    circular_dependencies: int


class P4Input(BaseModel):
    """Input for P4 – Phase Ordering & Scheduling."""

    idea_id: str
    work_dir: Path
    dependency_graph_file: Path


class P4Output(BaseModel):
    """Output of P4 – Phase Ordering & Scheduling."""

    schedule_file: Path
    phase_count: int
    estimated_tasks: int


class P5Input(BaseModel):
    """Input for P5 – PRD Generation."""

    idea_id: str
    work_dir: Path
    schedule_file: Path
    requirements_file: Path


class P5Output(BaseModel):
    """Output of P5 – PRD Generation."""

    prd_file: Path
    total_requirements: int
    phases_defined: int


class P6Input(BaseModel):
    """Input for P6 – Hygiene & Pre-flight."""

    work_dirs: list[Path]
    argv: list[str]
    stale_threshold_secs: int = 3600


class P6Output(BaseModel):
    """Output of P6 – Hygiene & Pre-flight.

    Wraps the HygieneReport from the promoted hygiene framework
    so downstream phases can inspect cleanup results.
    """

    class Config:
        arbitrary_types_allowed = True

    hygiene_report: Optional[HygieneReport] = None
    mode: str
    was_cleaned: bool
    was_skipped: bool
    remaining_args: list[str]
