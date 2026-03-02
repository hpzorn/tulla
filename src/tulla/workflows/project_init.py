"""Project initialisation workflows.

Provides one-shot migration helpers that bring existing ontology data
into alignment with evolving governance conventions, and the full
``init_project`` workflow that bootstraps a project from a CLAUDE.md file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tulla.namespaces import ARCH_NS, ISAQB_NS, PRD_NS, RDF_TYPE
from tulla.ports.claude import ClaudePort, ClaudeRequest
from tulla.ports.ontology import OntologyPort

logger = logging.getLogger(__name__)

RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"

# ---------------------------------------------------------------------------
# SPARQL: find ADRs that have no isaqb:scope annotation yet
# ---------------------------------------------------------------------------
_UNSCOPED_ADRS_QUERY = """\
SELECT ?adr WHERE {
  ?adr a isaqb:ArchitectureDecision .
  FILTER NOT EXISTS { ?adr isaqb:scope ?s }
}
"""


def migrate_existing_adrs(ontology_port: OntologyPort) -> int:
    """Annotate every unscoped ADR with ``isaqb:scope "idea"``.

    The function is **idempotent**: once an ADR carries a scope, the
    SPARQL filter excludes it, so a second invocation returns 0.

    Returns the number of ADRs that were annotated in *this* call.
    """
    result: dict[str, Any] = ontology_port.sparql_query(_UNSCOPED_ADRS_QUERY)
    bindings: list[dict[str, Any]] = result.get("results", [])

    count = 0
    for binding in bindings:
        adr_uri = binding.get("adr", "")
        if not adr_uri:
            continue

        ontology_port.add_triple(
            subject=adr_uri,
            predicate=f"{ISAQB_NS}scope",
            object="idea",
            is_literal=True,
        )
        count += 1
        logger.debug("Annotated %s with isaqb:scope 'idea'", adr_uri)

    logger.info("migrate_existing_adrs: annotated %d ADR(s)", count)
    return count


# ---------------------------------------------------------------------------
# ADR extraction prompt — encodes domain knowledge about architectural
# decisions vs coding conventions
# ---------------------------------------------------------------------------

_ADR_EXTRACTION_PROMPT = """\
You are an architecture-extraction agent. Given the CLAUDE.md project
instructions below, identify **architectural decisions** — choices that
constrain the solution space, affect quality attributes, or establish
cross-cutting conventions.

**Include** as ADRs:
- Technology selections (language, runtime, framework)
- Composition rules (ports & adapters, module boundaries)
- Data-format mandates (RDF, JSON-LD, Turtle)
- Quality-attribute trade-offs (favour simplicity over configurability)
- Cross-cutting patterns (error handling strategy, logging approach)

**Exclude** (these are coding conventions, not ADRs):
- Formatting preferences (indentation, line length)
- Commit message style
- Editor / IDE configuration
- Pure documentation rules

For each ADR output a JSON object with these keys:
  "title"       — short imperative sentence (e.g. "Use Python 3.11+ for new code")
  "context"     — forces, constraints, alternatives considered
  "consequences"— outcomes using (+), (-), (~) prefixes
  "arc42_section"— the arc42 section number (1-12) this decision is documented in

Return a JSON array of ADR objects. Output ONLY the JSON array, no markdown
fences, no commentary.

---
CLAUDE.md content:

{claude_md_content}
"""


# ---------------------------------------------------------------------------
# Dataclass for candidate ADRs returned by the LLM
# ---------------------------------------------------------------------------


@dataclass
class CandidateADR:
    """A candidate ADR extracted by the LLM, pending user confirmation."""

    title: str
    context: str
    consequences: str
    arc42_section: int = 9  # default: section 9 "Architecture Decisions"
    confirmed: bool = True  # default True; set False by interactive rejection


@dataclass
class InitProjectResult:
    """Outcome of the ``init_project`` workflow."""

    project_uri: str = ""
    adr_count: int = 0
    candidates: list[CandidateADR] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Interactive confirmation callback type
# ---------------------------------------------------------------------------

# Callback signature: (candidate) -> "accept" | "reject" | "edit" | "merge"
# For "edit", the callback should mutate the candidate in place before returning.
ConfirmCallback = Any  # Callable[[CandidateADR], str] — kept as Any for flexibility


def _parse_candidates(raw_text: str) -> list[CandidateADR]:
    """Parse LLM output into CandidateADR instances.

    Handles JSON arrays with optional markdown fences.
    """
    text = raw_text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM ADR output as JSON")
        return []

    if not isinstance(items, list):
        return []

    candidates: list[CandidateADR] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        candidates.append(CandidateADR(
            title=item.get("title", ""),
            context=item.get("context", ""),
            consequences=item.get("consequences", ""),
            arc42_section=int(item.get("arc42_section", 9)),
        ))
    return candidates


def _default_confirm(candidate: CandidateADR) -> str:
    """Default non-interactive confirmation — accepts all candidates."""
    return "accept"


# ---------------------------------------------------------------------------
# Core workflow: init_project
# ---------------------------------------------------------------------------


def init_project(
    ontology_port: OntologyPort,
    claude_port: ClaudePort,
    project_id: str,
    claude_md_path: Path,
    *,
    interactive: bool = False,
    confirm_fn: ConfirmCallback | None = None,
) -> InitProjectResult:
    """Orchestrate full project initialisation from a CLAUDE.md file.

    Steps:
        1. Read CLAUDE.md content.
        2. Send content to LLM with ADR extraction prompt.
        3. If interactive, present each extracted ADR for confirmation.
        4. Create the project instance (rdf:type prd:Project, rdfs:label,
           prd:projectId).
        5. Store each confirmed ADR as isaqb:ArchitectureDecision with
           isaqb:scope "project" and prd:hasADR link from project.
        6. Add isaqb:documentedIn links to arc42 sections.

    Parameters:
        ontology_port: Ontology port for triple storage.
        claude_port: Claude port for LLM invocation.
        project_id: Unique project identifier.
        claude_md_path: Path to the CLAUDE.md file.
        interactive: If True, use confirm_fn for each candidate ADR.
        confirm_fn: Callback ``(CandidateADR) -> str`` returning one of
            "accept", "reject", "edit", "merge".  Defaults to accept-all.

    Returns:
        An :class:`InitProjectResult` with the project URI and ADR count.
    """
    result = InitProjectResult()

    # (1) Read CLAUDE.md
    try:
        claude_md_content = claude_md_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to read CLAUDE.md at %s: %s", claude_md_path, exc)
        return result

    # (2) Send to LLM with ADR extraction prompt
    prompt = _ADR_EXTRACTION_PROMPT.format(claude_md_content=claude_md_content)
    llm_result = claude_port.run(ClaudeRequest(prompt=prompt))
    candidates = _parse_candidates(llm_result.output_text)
    result.candidates = candidates

    if not candidates:
        logger.warning("No ADR candidates extracted from %s", claude_md_path)

    # (3) Interactive confirmation
    if interactive and confirm_fn is not None:
        for candidate in candidates:
            action = confirm_fn(candidate)
            if action == "reject":
                candidate.confirmed = False
            # "accept", "edit", "merge" all keep confirmed=True
            # For "edit", confirm_fn is expected to mutate candidate in place
    # Non-interactive: all candidates remain confirmed=True (default)

    confirmed = [c for c in candidates if c.confirmed]

    # (4) Create project instance
    project_uri = f"{PRD_NS}project-{project_id}"
    result.project_uri = project_uri

    ontology_port.add_triple(
        subject=project_uri,
        predicate=RDF_TYPE,
        object=f"{PRD_NS}Project",
    )
    ontology_port.add_triple(
        subject=project_uri,
        predicate=RDFS_LABEL,
        object=f"Project {project_id}",
        is_literal=True,
    )
    ontology_port.add_triple(
        subject=project_uri,
        predicate=f"{PRD_NS}projectId",
        object=project_id,
        is_literal=True,
    )

    # (5) Store each confirmed ADR
    for idx, adr in enumerate(confirmed, start=1):
        adr_uri = f"{ARCH_NS}adr-{project_id}-{idx}"

        # rdf:type isaqb:ArchitectureDecision
        ontology_port.add_triple(
            subject=adr_uri,
            predicate=RDF_TYPE,
            object=f"{ISAQB_NS}ArchitectureDecision",
        )
        # rdfs:label
        ontology_port.add_triple(
            subject=adr_uri,
            predicate=RDFS_LABEL,
            object=f"ADR-{project_id}-{idx}: {adr.title}",
            is_literal=True,
        )
        # isaqb:context
        ontology_port.add_triple(
            subject=adr_uri,
            predicate=f"{ISAQB_NS}context",
            object=adr.context,
            is_literal=True,
        )
        # isaqb:decisionStatus — Proposed
        ontology_port.add_triple(
            subject=adr_uri,
            predicate=f"{ISAQB_NS}decisionStatus",
            object=f"{ISAQB_NS}StatusProposed",
        )
        # isaqb:consequences
        ontology_port.add_triple(
            subject=adr_uri,
            predicate=f"{ISAQB_NS}consequences",
            object=adr.consequences,
            is_literal=True,
        )
        # isaqb:scope "project"
        ontology_port.add_triple(
            subject=adr_uri,
            predicate=f"{ISAQB_NS}scope",
            object="project",
            is_literal=True,
        )
        # prd:hasADR link from project to ADR
        ontology_port.add_triple(
            subject=project_uri,
            predicate=f"{PRD_NS}hasADR",
            object=adr_uri,
        )

        # (6) isaqb:documentedIn link to arc42 section
        section_num = adr.arc42_section
        arc42_uri = f"{ISAQB_NS}Arc42_{section_num:02d}"
        ontology_port.add_triple(
            subject=adr_uri,
            predicate=f"{ISAQB_NS}documentedIn",
            object=arc42_uri,
        )

        logger.debug("Stored project ADR %s: %s", adr_uri, adr.title)

    result.adr_count = len(confirmed)
    logger.info(
        "init_project: created project %s with %d ADR(s)",
        project_uri,
        result.adr_count,
    )
    return result


# ---------------------------------------------------------------------------
# ADR promotion: idea scope → project scope
# ---------------------------------------------------------------------------


def promote_adr(
    ontology_port: OntologyPort,
    adr_uri: str,
    project_uri: str,
) -> None:
    """Promote an ADR from idea scope to project scope.

    Updates ``isaqb:scope`` from ``"idea"`` to ``"project"`` and adds a
    ``prd:hasADR`` link from the project to the ADR.

    This is a one-way promotion — the old ``"idea"`` scope triple is
    removed and replaced with ``"project"``.

    Parameters:
        ontology_port: The ontology port for triple operations.
        adr_uri: Full URI of the ADR to promote.
        project_uri: Full URI of the project to link to.
    """
    # Remove old scope triple via SPARQL UPDATE.
    # add_triple stores in the phases named graph, so DELETE must target it.
    _PHASES_GRAPH = "http://semantic-tool-use.org/graphs/phases"
    _REMOVE_SCOPE_QUERY = f"""\
DELETE WHERE {{
  GRAPH <{_PHASES_GRAPH}> {{
    <{adr_uri}> isaqb:scope ?old_scope .
  }}
}}"""

    try:
        ontology_port.sparql_update(_REMOVE_SCOPE_QUERY)
    except Exception as exc:
        logger.debug(
            "SPARQL DELETE for old scope failed (may not exist): %s", exc,
        )

    # Add new scope "project"
    ontology_port.add_triple(
        subject=adr_uri,
        predicate=f"{ISAQB_NS}scope",
        object="project",
        is_literal=True,
    )

    # Add prd:hasADR link from project
    ontology_port.add_triple(
        subject=project_uri,
        predicate=f"{PRD_NS}hasADR",
        object=adr_uri,
    )

    logger.info("Promoted %s to project scope, linked to %s", adr_uri, project_uri)
