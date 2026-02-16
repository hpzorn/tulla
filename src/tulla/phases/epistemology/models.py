"""Pydantic data models for the Epistemology phase modes."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class EpistemologyOutput(BaseModel):
    """Output of any epistemology mode — generative idea creation."""

    output_file: Path
    ideas_generated: int = Field(json_schema_extra={"preserves_intent": True})
    frameworks_used: list[str]
    mode: str = Field(json_schema_extra={"preserves_intent": True})
