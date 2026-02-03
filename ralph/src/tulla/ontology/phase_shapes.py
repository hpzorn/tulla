"""SHACL Shape Registry: maps phase IDs to their SHACL shape URIs.

Imported by pipeline integration code to determine whether SHACL
validation should run for a given phase.

Architecture decision: arch:adr-67-6
"""

from __future__ import annotations

PHASE_SHAPES: dict[str, str] = {
    "d5": "phase:D5OutputShape",
    "r5": "phase:R5OutputShape",
    "p3": "phase:P3OutputShape",
}


def get_shape_for_phase(phase_id: str) -> str | None:
    """Return the SHACL shape URI for *phase_id*, or ``None`` if unregistered."""
    return PHASE_SHAPES.get(phase_id)
