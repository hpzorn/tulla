"""Shared helpers for epistemology phase modes."""

from __future__ import annotations

import re
from typing import Any

from tulla.core.phase import ParseError, PhaseContext

from .models import EpistemologyOutput


def extract_section(content: str, heading: str) -> str:
    """Extract content under a markdown heading until the next heading."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else ""


def count_idea_headings(content: str) -> int:
    """Count ``## Idea N:`` or ``## Synthesis N:`` headings."""
    return len(re.findall(r"^##\s+(?:Idea|Synthesis)\s+\d+:", content, re.MULTILINE))


def parse_epistemology_output(
    phase_id: str,
    mode: str,
    ctx: PhaseContext,
    raw: Any,
    output_filename: str,
    frameworks: list[str],
) -> EpistemologyOutput:
    """Shared parse_output logic for all epistemology modes."""
    output_file = ctx.work_dir / output_filename

    if not output_file.exists():
        raise ParseError(
            f"{output_filename} not found in {ctx.work_dir}",
            raw_output=raw,
            context={"work_dir": str(ctx.work_dir)},
        )

    content = output_file.read_text(encoding="utf-8")
    ideas_generated = count_idea_headings(content)

    return EpistemologyOutput(
        output_file=output_file,
        ideas_generated=ideas_generated,
        frameworks_used=frameworks,
        mode=mode,
    )
