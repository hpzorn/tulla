"""RDF namespace URIs and prefix utilities.

Single source of truth for all namespace mappings used across Tulla.
Replaces duplicated dicts formerly in ``p6.py`` and ``find.py``.
"""

from __future__ import annotations

# Domain namespaces
PRD_NS = "http://impl-ralph.io/prd#"
TRACE_NS = "http://impl-ralph.io/trace#"
ISAQB_NS = "http://impl-ralph.io/isaqb#"
PHASE_NS = "http://impl-ralph.io/phase#"
ARCH_NS = "http://impl-ralph.io/arch#"

# Well-known URIs
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
PHASE_ONTOLOGY_URI = "ontology://phase-ontology"

# Full URI -> compact prefix (used by p6 hydration)
PREFIXES: dict[str, str] = {
    PRD_NS: "prd:",
    TRACE_NS: "trace:",
    ISAQB_NS: "isaqb:",
    PHASE_NS: "phase:",
    ARCH_NS: "arch:",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/2001/XMLSchema#": "xsd:",
}

# Compact prefix -> full URI (used by find.py SPARQL)
REVERSE_PREFIXES: dict[str, str] = {v: k for k, v in PREFIXES.items()}


def compact_uri(uri: str) -> str:
    """Compact a full URI into prefixed form.

    Returns the original string unchanged if no prefix matches.
    """
    for full, prefix in PREFIXES.items():
        if uri.startswith(full):
            return prefix + uri[len(full):]
    return uri
