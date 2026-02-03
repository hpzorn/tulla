"""Pydantic data models for the Research phase (R1-R6)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from tulla.core.intent import IntentField


class ResearchInput(BaseModel):
    """Input parameters for a research phase run."""

    idea_id: str
    work_dir: Path
    planning_output_dir: Path


class R1Output(BaseModel):
    """Output of R1 - Research Question Refinement."""

    output_file: Path
    questions_refined: int


class R2Output(BaseModel):
    """Output of R2 - Source Identification."""

    output_file: Path
    sources_identified: int


class R3Output(BaseModel):
    """Output of R3 - Research Questions."""

    output_file: Path
    research_questions: int


class R4Output(BaseModel):
    """Output of R4 - Literature Review."""

    output_file: Path
    papers_reviewed: int
    rqs_addressed: int


class R5Output(BaseModel):
    """Output of R5 - Experiments & Prototyping.

    R5 has extended timeout (120 min) and acceptEdits permission mode.
    Retry loop on experiment failure maps to max_retries on the phase.
    """

    output_file: Path
    experiments_run: int = IntentField(description="Number of experiments executed")
    experiments_passed: int = IntentField(description="Number of experiments that passed")


class R6Output(BaseModel):
    """Output of R6 - Research Synthesis."""

    output_file: Path
    findings_count: int
    recommendation: str
