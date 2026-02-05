"""Planning phase shared constants and helpers."""

from __future__ import annotations

from typing import Any

PLANNING_IDENTITY = (
    "You are Planning-Tulla, a systematic planning agent running as a "
    "Claude Code subprocess.\n"
    "\n"
    "**Capabilities**: You have access to file tools (Read, Write, Glob, Grep), "
    "ontology queries and fact storage, and architecture schema lookup. "
    "You can read discovery artifacts, research findings, and prior planning "
    "outputs from the work directory.\n"
    "\n"
    "**Context**: Prior phases (discovery, research) may have persisted facts "
    "to the ontology A-box. When present, a Northstar section shows the idea's "
    "core definition, and an Upstream Facts section provides structured data "
    "from earlier phases to inform your planning.\n"
    "\n"
)


def build_northstar_section(grouped_facts: dict[str, dict[str, Any]]) -> str:
    """Extract northstar from D5 upstream facts and render as a prompt section.

    Looks for ``grouped["d5"]["northstar"]``.  If present, renders a
    prominent ``## Northstar`` section.  Returns empty string otherwise.
    """
    northstar = ""
    if grouped_facts:
        northstar = grouped_facts.get("d5", {}).get("northstar", "")

    if northstar:
        return f"## Northstar\n{northstar}\n\n"
    return ""
