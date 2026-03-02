"""Pydantic data models for the Planning phase (P1–P6)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from tulla.core.intent import IntentField


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
    total_dependencies: int = IntentField(description="Total number of requirement dependencies")
    circular_dependencies: int = IntentField(
        description="Number of circular dependencies detected",
    )
    architecture_decisions: str = IntentField(
        default="[]",
        description="JSON list of {title, decision, rationale} from ADRs",
    )
    quality_goals: str = IntentField(
        default="[]",
        description="JSON list of {attribute, priority} from quality goals",
    )


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
    coarse_tasks: list[dict[str, Any]] = Field(default_factory=list)
    granularity_passed: bool = True


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
    """Input for P6 – Export PRD to RDF."""

    idea_id: str
    work_dir: Path
    p4_file: Path


class P6Output(BaseModel):
    """Output of P6 – Export PRD to RDF.

    Captures the results of exporting the implementation plan (P4)
    into RDF triples stored in the ontology A-box via ``store_fact``.
    """

    turtle_file: Path
    summary_file: Path
    requirements_exported: int
    prd_context: str
    adr_links: int = 0
    quality_links: int = 0
    triples_stored: int = 0
    coarse_requirements: list[dict[str, Any]] = Field(default_factory=list)
    granularity_passed: bool = True
