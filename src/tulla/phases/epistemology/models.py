"""Pydantic data models for the Epistemology phase modes."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class EpistemologyOutput(BaseModel):
    """Output of any epistemology mode — generative idea creation."""

    output_file: Path
    ideas_generated: int
    frameworks_used: list[str]
    mode: str
