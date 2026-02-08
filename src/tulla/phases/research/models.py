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
    questions_refined: int = IntentField(
        description="Number of research questions refined",
    )
    research_questions: str = IntentField(
        default="[]",
        description="JSON list of {id, question, methodology, acceptance_criteria}",
    )


class R2Output(BaseModel):
    """Output of R2 - Source Identification."""

    output_file: Path
    sources_identified: int = IntentField(
        description="Number of sources identified across all RQs",
    )
    source_map: str = IntentField(
        default="[]",
        description="JSON list of {rq, source, type, relevance}",
    )
    source_gaps: str = IntentField(
        default="",
        description="RQs where sources are scarce — may need experimentation",
    )


class R3Output(BaseModel):
    """Output of R3 - Research Questions."""

    output_file: Path
    research_questions: int = IntentField(
        description="Number of research questions investigated",
    )
    rq_answers: str = IntentField(
        default="[]",
        description="JSON list of {id, status, confidence, answer}",
    )
    remaining_unknowns: str = IntentField(
        default="",
        description="Questions needing further investigation via experiment/prototype",
    )


class R4Output(BaseModel):
    """Output of R4 - Literature Review."""

    output_file: Path
    papers_reviewed: int = IntentField(
        description="Number of papers/sources reviewed in depth",
    )
    rqs_addressed: int = IntentField(
        description="Number of research questions addressed by review",
    )
    key_findings: str = IntentField(
        default="[]",
        description="JSON list of {rq, recommendation, finding_summary}",
    )


class R5Output(BaseModel):
    """Output of R5 - Experiments & Prototyping.

    R5 has extended timeout (120 min) and acceptEdits permission mode.
    Retry loop on experiment failure maps to max_retries on the phase.
    """

    output_file: Path
    experiments_run: int = IntentField(description="Number of experiments executed")
    experiments_passed: int = IntentField(description="Number of experiments that passed")
    experiment_results: str = IntentField(
        default="[]",
        description="JSON list of {title, rq, result, finding}",
    )
    impl_implications: str = IntentField(
        default="",
        description="How experiment findings affect the implementation plan",
    )


class R6Output(BaseModel):
    """Output of R6 - Research Synthesis."""

    output_file: Path
    findings_count: int = IntentField(
        description="Number of research findings synthesised",
    )
    recommendation: str = IntentField(
        description="Overall recommendation: proceed / revise plan / more research needed",
    )
    synthesised_answers: str = IntentField(
        default="[]",
        description="JSON list of {rq, answer, confidence, implication}",
    )
    risks: str = IntentField(
        default="[]",
        description="JSON list of {risk, likelihood, impact, mitigation}",
    )
