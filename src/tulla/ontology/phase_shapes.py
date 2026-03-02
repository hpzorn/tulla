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

# @principle:OpenClosedPrinciple -- new phases register shapes
#   by adding a dict entry; consumers never change
# @principle:HighCohesion -- single-purpose registry mapping
#   phase IDs to SHACL shape URIs
# @principle:InformationHiding -- get_shape_for_phase hides
#   dict lookup so callers need not know the storage
# @principle:LooseCoupling -- callers depend only on
#   get_shape_for_phase, never on the PHASE_SHAPES dict directly
# @principle:SingleResponsibility -- module owns shape-URI
#   resolution exclusively; no persistence or validation logic

from __future__ import annotations

from tulla.namespaces import PHASE_NS

PHASE_SHAPES: dict[str, str] = {
    "d1": f"{PHASE_NS}D1OutputShape",
    "d2": f"{PHASE_NS}D2OutputShape",
    "d3": f"{PHASE_NS}D3OutputShape",
    "d4": f"{PHASE_NS}D4OutputShape",
    "d5": f"{PHASE_NS}D5OutputShape",
    "r1": f"{PHASE_NS}R1OutputShape",
    "r2": f"{PHASE_NS}R2OutputShape",
    "r3": f"{PHASE_NS}R3OutputShape",
    "r4": f"{PHASE_NS}R4OutputShape",
    "r5": f"{PHASE_NS}R5OutputShape",
    "r6": f"{PHASE_NS}R6OutputShape",
    "p3": f"{PHASE_NS}P3OutputShape",
    "lw-trace": f"{PHASE_NS}LWTraceOutputShape",
}


def get_shape_for_phase(phase_id: str) -> str | None:
    """Return the SHACL shape URI for *phase_id*, or ``None`` if unregistered."""
    return PHASE_SHAPES.get(phase_id)
