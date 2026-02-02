"""Pydantic data models for the Epistemology phase modes."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class PoolOutput(BaseModel):
    """Output of epistemology pool mode — idea-pool health assessment."""

    output_file: Path
    ideas_analysed: int
    issues_found: int


class IdeaOutput(BaseModel):
    """Output of epistemology idea mode — single-idea epistemic review."""

    output_file: Path
    claims_checked: int
    issues_found: int


class DomainOutput(BaseModel):
    """Output of epistemology domain mode — domain coherence check."""

    output_file: Path
    domains_analysed: int
    incoherences_found: int


class ProblemOutput(BaseModel):
    """Output of epistemology problem mode — problem-framing review."""

    output_file: Path
    problems_reviewed: int
    reframings_suggested: int


class ContradictionOutput(BaseModel):
    """Output of epistemology contradiction mode — contradiction detection."""

    output_file: Path
    pairs_checked: int
    contradictions_found: int


class SignalOutput(BaseModel):
    """Output of epistemology signal mode — weak-signal scan."""

    output_file: Path
    signals_detected: int
    actionable_signals: int
