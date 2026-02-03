"""SHACL Shape Registry: maps phase IDs to their SHACL shape URIs.

Imported by pipeline integration code to determine whether SHACL
validation should run for a given phase.

Architecture decision: arch:adr-67-6

Ontology-server registration (prd:req-67-4-3):
    The SHACL shapes live in ``tulla/ontology/phase-ontology.ttl``
    (single source of truth).  A chain of symlinks makes this file
    visible to the ontology-server at startup, following the same
    pattern used by ``prd-ontology.ttl``:

    1. ``ideasralph/ontologies/phase-ontology.ttl``
       → symlink to the source file in this package.

    2. ``semantic-tool-use/ontology/domain/visual-artifacts/phase-ontology.ttl``
       → symlink to (1).  The server's ``--ontology-path`` points here;
         ``OntologyStore.load_directory()`` picks it up via
         ``rglob("*.ttl")``, registering it as ``ontology://phase-ontology``.

    3. ``semantic-tool-use/src/ontology_server/shapes/phase-ontology.ttl``
       → symlink to the source file.  The server's ``--shapes-path``
         points here; ``SHACLValidator.load_shapes()`` picks it up via
         ``glob("*.ttl")``, making shapes like ``phase:D5OutputShape``
         available to ``validate_instance``.

    No server config change is needed; the existing ``rglob``/``glob``
    scans discover the symlinks automatically on (re)start.
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
