"""Phase fact persistence: dataclasses, persister, and upstream collection.

Provides :class:`PersistResult` — the return type used by the persister to
communicate what happened during a persist-validate-rollback cycle — and
:class:`PhaseFactPersister` which orchestrates the extraction, storage,
validation, and optional rollback of intent-annotated phase output fields.

Also provides :func:`collect_upstream_facts` for SPARQL-based collection of
prior-phase facts, :func:`collect_project_decisions` for SPARQL-based
collection of project-scoped architecture decisions (req-69-1-5),
:func:`group_upstream_facts` for transforming flat SPO triples into grouped
``{phase_id: {field: typed_value}}`` dicts (arch:adr-73-1), and
:func:`traverse_chain` for SPARQL property-path traversal of
``trace:tracesTo`` chains (arch:adr-67-4).

Architecture decisions: arch:adr-67-1, arch:adr-67-2, arch:adr-67-4, arch:adr-73-1, arch:adr-73-5
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from tulla.core.intent import extract_intent_fields
from tulla.core.phase import PhaseResult
from tulla.namespaces import ARCH_NS, PHASE_NS, TRACE_NS, RDF_TYPE
from tulla.ports.ontology import OntologyPort

logger = logging.getLogger(__name__)


@dataclass
class PersistResult:
    """Outcome of persisting phase facts to the ontology store.

    Attributes:
        stored_count: Number of triples successfully stored.
        validation_passed: None if no SHACL shape exists for the phase,
            True if validation succeeded, False if it failed.
        validation_errors: SHACL violation messages; empty when
            validation passed or no shape exists.
        rolled_back: True if stored triples were rolled back because
            validation failed.
    """

    stored_count: int = 0
    validation_passed: bool | None = None
    validation_errors: list[str] = field(default_factory=list)
    rolled_back: bool = False


class PhaseFactPersister:
    """Persists intent-annotated phase output fields as direct graph triples.

    Uses ``add_triple`` to write real SPO edges into the phase-ontology
    graph, enabling SPARQL property-path traversal and SHACL validation.

    Follows the idempotent-write pattern: ``remove_triples_by_subject``
    clears stale triples before storing fresh ones, making the operation
    safe for pipeline resume/rerun.

    Parameters:
        ontology: The :class:`OntologyPort` used for all triple/validate
            operations.
    """

    def __init__(self, ontology: OntologyPort) -> None:
        self._ontology = ontology

    def persist(
        self,
        idea_id: str,
        phase_id: str,
        phase_result: PhaseResult[Any],
        predecessor_phase_id: str | None,
        shacl_shape_id: str | None,
    ) -> PersistResult:
        """Persist intent fields from a phase result as direct graph triples.

        Steps:
            1. Extract intent fields — return no-op if empty.
            2. Compute full-URI subject.
            3. Idempotent cleanup via ``remove_triples_by_subject``.
            4. Store ``rdf:type phase:PhaseOutput`` for SHACL targeting.
            5. Store each intent field as ``phase:preserves-{name}`` literal.
            6. Store ``phase:producedBy`` and ``phase:forRequirement`` metadata.
            7. If predecessor given, store ``trace:tracesTo`` graph edge.
            8. If SHACL shape given, validate and roll back on failure.

        Returns:
            A :class:`PersistResult` describing the outcome.
        """
        # (1) Extract intent fields from phase_result.data
        intent_fields = extract_intent_fields(phase_result.data)
        if not intent_fields:
            logger.debug(
                "No intent fields for phase %s idea %s — no-op",
                phase_id,
                idea_id,
            )
            return PersistResult(stored_count=0)

        # (2) Compute full-URI subject
        subject = f"{PHASE_NS}{idea_id}-{phase_id}"

        # (3) Idempotent cleanup — wipe all prior triples for this subject
        # @pattern:EventSourcing -- Idempotent cleanup via remove_triples_by_subject ensures pipeline resume/rerun never duplicates A-Box triples
        cleared = self._ontology.remove_triples_by_subject(subject)
        if cleared:
            logger.info(
                "Cleared %d existing triples for subject %s",
                cleared,
                subject,
            )

        stored = 0

        # (4) rdf:type for SHACL sh:targetClass matching
        self._ontology.add_triple(
            subject, RDF_TYPE, f"{PHASE_NS}PhaseOutput",
        )
        stored += 1

        # (5) Intent fields as direct literal edges
        # @pattern:EventSourcing -- Skip None values to avoid persisting "None" literals, aligning with SHACL minCount=0 for optional fields (arch:adr-73-4)
        for field_name, value in intent_fields.items():
            if value is None:
                continue
            self._ontology.add_triple(
                subject,
                f"{PHASE_NS}preserves-{field_name}",
                str(value),
                is_literal=True,
            )
            stored += 1

        # (6) Metadata
        self._ontology.add_triple(
            subject, f"{PHASE_NS}producedBy", phase_id, is_literal=True,
        )
        self._ontology.add_triple(
            subject, f"{PHASE_NS}forRequirement", idea_id, is_literal=True,
        )
        stored += 2

        # (7) Optional trace:tracesTo predecessor — real graph edge
        if predecessor_phase_id is not None:
            pred_uri = f"{PHASE_NS}{idea_id}-{predecessor_phase_id}"
            self._ontology.add_triple(
                subject, f"{TRACE_NS}tracesTo", pred_uri,
            )
            stored += 1

        # (8) Optional SHACL validation + rollback
        if shacl_shape_id is not None:
            try:
                result = self._ontology.validate_instance(
                    subject, shacl_shape_id,
                )
            except Exception as exc:
                logger.error(
                    "validate_instance raised for %s shape %s: %s",
                    subject,
                    shacl_shape_id,
                    exc,
                )
                self._ontology.remove_triples_by_subject(subject)
                return PersistResult(
                    stored_count=stored,
                    validation_passed=False,
                    validation_errors=[str(exc)],
                    rolled_back=True,
                )

            conforms = result.get("conforms", True)
            violations = result.get("violations", [])

            if not conforms:
                logger.warning(
                    "SHACL validation failed for %s — rolling back %d triples",
                    subject,
                    stored,
                )
                self._ontology.remove_triples_by_subject(subject)
                return PersistResult(
                    stored_count=stored,
                    validation_passed=False,
                    validation_errors=[str(v) for v in violations],
                    rolled_back=True,
                )

            return PersistResult(
                stored_count=stored,
                validation_passed=True,
            )

        return PersistResult(stored_count=stored)


def collect_upstream_facts(
    ontology_port: OntologyPort,
    idea_id: str,
    phase_sequence: list[str],
    current_phase_id: str,
) -> list[dict[str, Any]]:
    """Collect facts from all phases preceding *current_phase_id* via SPARQL.

    Executes a single SPARQL query to fetch all triples for the given
    *idea_id*, then filters to upstream phases only based on phase_sequence.

    Returns a flat list of fact dicts ordered by phase sequence.
    If *current_phase_id* is the first phase or is not found in the
    sequence, an empty list is returned.
    """
    try:
        current_idx = phase_sequence.index(current_phase_id)
    except ValueError:
        logger.warning(
            "current_phase_id %r not found in phase_sequence — "
            "returning empty upstream facts",
            current_phase_id,
        )
        return []

    if current_idx == 0:
        return []

    upstream_ids = set(phase_sequence[:current_idx])

    # Phase facts are stored in the phases named graph, not the default graph.
    phases_graph = "http://semantic-tool-use.org/graphs/phases"
    query = (
        f'SELECT ?s ?p ?o WHERE {{\n'
        f'  GRAPH <{phases_graph}> {{\n'
        f'    ?s phase:forRequirement "{idea_id}" .\n'
        f'    ?s ?p ?o .\n'
        f'  }}\n'
        f'}}'
    )

    try:
        result = ontology_port.sparql_query(query)
    except Exception as exc:
        logger.warning("SPARQL query for upstream facts failed: %s", exc)
        return []

    # Group results by subject, filter to upstream phases only
    bindings = result.get("results", [])
    all_facts: list[dict[str, Any]] = []

    for binding in bindings:
        subj = binding.get("s", "")
        # Extract phase_id from subject URI: {PHASE_NS}{idea_id}-{phase_id}
        prefix = f"{PHASE_NS}{idea_id}-"
        if subj.startswith(prefix):
            pid = subj[len(prefix):]
            if pid in upstream_ids:
                all_facts.append({
                    "subject": subj,
                    "predicate": binding.get("p", ""),
                    "object": binding.get("o", ""),
                })

    return all_facts


# ---------------------------------------------------------------------------
# Project-scoped decision collection (req-69-1-5)
# ---------------------------------------------------------------------------


def collect_project_decisions(
    ontology_port: OntologyPort,
    project_id: str,
) -> list[dict[str, Any]]:
    """Collect project-scoped architecture decisions via SPARQL.

    Executes a SPARQL query with dual filtering — scope-based
    (``isaqb:scope "project"``) UNION URI-based (``STRSTARTS``) — for
    robustness against missing scope annotations.

    The query selects ``?adr``, ``?title``, ``?context``, ``?status``,
    ``?consequences``, and ``GROUP_CONCAT`` of ``isaqb:addresses`` quality
    attributes.

    Parameters:
        ontology_port: The ontology port to query.
        project_id: The project identifier (used for URI prefix matching).

    Returns:
        A list of dicts with keys: ``id``, ``title``, ``decision``,
        ``quality_attributes``, ``scope``, ``status``.
        On query failure, returns an empty list with a log warning —
        matching the error handling pattern of :func:`collect_upstream_facts`.
    """
    query = f"""\
SELECT ?adr ?title ?context ?status ?consequences
       (GROUP_CONCAT(DISTINCT ?qa; SEPARATOR=", ") AS ?quality_attributes)
WHERE {{
  {{
    ?adr a isaqb:ArchitectureDecision .
    ?adr isaqb:scope "project" .
  }}
  UNION
  {{
    ?adr a isaqb:ArchitectureDecision .
    FILTER(STRSTARTS(STR(?adr), "{ARCH_NS}adr-{project_id}-"))
  }}
  ?adr rdfs:label ?title .
  OPTIONAL {{ ?adr isaqb:context ?context }}
  OPTIONAL {{ ?adr isaqb:decisionStatus ?status }}
  OPTIONAL {{ ?adr isaqb:consequences ?consequences }}
  OPTIONAL {{ ?adr isaqb:addresses ?qa }}
}}
GROUP BY ?adr ?title ?context ?status ?consequences"""

    try:
        result = ontology_port.sparql_query(query)
    except Exception as exc:
        logger.warning("SPARQL query for project decisions failed: %s", exc)
        return []

    bindings = result.get("results", [])
    decisions: list[dict[str, Any]] = []

    for row in bindings:
        adr_uri = row.get("adr", "")
        adr_id = adr_uri.split("#")[-1] if "#" in adr_uri else adr_uri

        qa_raw = row.get("quality_attributes", "")
        qa_list = [q.strip() for q in qa_raw.split(",") if q.strip()] if qa_raw else []

        # Determine scope: if the URI matches project pattern, it's "project";
        # otherwise rely on the scope annotation.
        scope = "project"

        decisions.append({
            "id": adr_id,
            "title": row.get("title", ""),
            "decision": row.get("consequences", ""),
            "quality_attributes": qa_list,
            "scope": scope,
            "status": row.get("status", ""),
        })

    return decisions


# ---------------------------------------------------------------------------
# Upstream fact grouping (arch:adr-73-1, arch:adr-73-5)
# ---------------------------------------------------------------------------

_PRESERVES_PREFIX = f"{PHASE_NS}preserves-"


def _try_coerce(value: str) -> Any:
    """Attempt to coerce a string value to a richer Python type.

    Tries conversions in order: int, float, bool, JSON (via json.loads),
    then falls back to the original string.  This handles all current
    scalar IntentField types persisted as RDF literals.
    """
    # int
    try:
        return int(value)
    except (ValueError, TypeError):
        pass

    # float
    try:
        return float(value)
    except (ValueError, TypeError):
        pass

    # bool (RDF/SPARQL canonical forms)
    if value.lower() in ("true", "false"):
        return value.lower() == "true"

    # JSON compound value (list, dict, etc.)
    try:
        parsed = json.loads(value)
        # Only accept compound types — scalars are handled above
        if isinstance(parsed, (list, dict)):
            return parsed
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Fallback: plain string
    return value


def group_upstream_facts(
    raw_facts: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    """Group flat SPO triples into a nested dict keyed by phase then field.

    Transforms the flat list returned by :func:`collect_upstream_facts` into::

        {
            "d1": {"tools_found": 5, "mcp_servers_found": 3},
            "d2": {"persona_count": 3},
        }

    Only ``phase:preserves-*`` predicates are included; metadata predicates
    (``producedBy``, ``forRequirement``, ``rdf:type``, ``trace:tracesTo``)
    are silently skipped.  Values are auto-coerced via :func:`_try_coerce`.

    Parameters:
        raw_facts: Flat list of ``{"subject": ..., "predicate": ..., "object": ...}``
            dicts as returned by :func:`collect_upstream_facts`.

    Returns:
        Nested dict ``{phase_id: {field_name: typed_value}}``.
        Empty dict for empty input.
    """
    if not raw_facts:
        return {}

    grouped: dict[str, dict[str, Any]] = {}

    for fact in raw_facts:
        predicate: str = fact.get("predicate", "")

        # Skip non-preserves predicates (metadata, rdf:type, trace, etc.)
        if not predicate.startswith(_PRESERVES_PREFIX):
            continue

        field_name = predicate[len(_PRESERVES_PREFIX):]

        # Extract phase_id from subject URI: {PHASE_NS}{idea_id}-{phase_id}
        subject: str = fact.get("subject", "")
        # Find the last '-' after the PHASE_NS prefix to split idea_id-phase_id
        after_ns = subject[len(PHASE_NS):] if subject.startswith(PHASE_NS) else ""
        dash_idx = after_ns.find("-")
        if dash_idx == -1:
            continue
        phase_id = after_ns[dash_idx + 1:]

        raw_value: str = fact.get("object", "")
        typed_value = _try_coerce(raw_value)

        if phase_id not in grouped:
            grouped[phase_id] = {}
        grouped[phase_id][field_name] = typed_value

    return grouped


_TRAVERSE_MAX_DEPTH = 20


def traverse_chain(
    ontology_port: OntologyPort,
    idea_id: str,
    phase_id: str,
    *,
    max_depth: int = _TRAVERSE_MAX_DEPTH,
) -> list[dict[str, Any]]:
    """Walk the ``trace:tracesTo`` chain using SPARQL property paths.

    Executes a SPARQL query with ``trace:tracesTo+`` to find all ancestors
    of the starting subject in one query, then fetches their triples.

    The returned list is ordered from *most recent* phase (the starting
    subject) toward the *origin* (the phase with no ``tracesTo`` link),
    i.e. reverse chronological order.

    A ``max_depth`` guard (default 20) limits the property path depth.

    Parameters:
        ontology_port: The ontology port to query.
        idea_id: The idea identifier.
        phase_id: The phase identifier to start traversal from.
        max_depth: Maximum hops before termination (default 20).

    Returns:
        Ordered list of dicts, each containing ``"subject"`` (the phase URI)
        and ``"facts"`` (list of fact dicts for that subject).
    """
    subject = f"{PHASE_NS}{idea_id}-{phase_id}"

    # Step 1: Find all ancestors via property path
    path_expr = f"trace:tracesTo{{1,{max_depth}}}" if max_depth != _TRAVERSE_MAX_DEPTH else "trace:tracesTo+"
    ancestor_query = (
        f"SELECT ?ancestor WHERE {{\n"
        f"  <{subject}> {path_expr} ?ancestor .\n"
        f"}}"
    )

    try:
        ancestor_result = ontology_port.sparql_query(ancestor_query)
    except Exception as exc:
        logger.warning(
            "SPARQL ancestor query failed for %s: %s", subject, exc,
        )
        return []

    # Build ordered ancestor list
    ancestor_uris: list[str] = []
    for binding in ancestor_result.get("results", []):
        uri = binding.get("ancestor", "")
        if uri and uri not in ancestor_uris:
            ancestor_uris.append(uri)

    # Full chain: starting subject + ancestors in order
    all_subjects = [subject] + ancestor_uris

    # Step 2: Fetch facts for each subject
    chain: list[dict[str, Any]] = []
    for subj in all_subjects:
        facts_query = (
            f"SELECT ?p ?o WHERE {{\n"
            f"  <{subj}> ?p ?o .\n"
            f"}}"
        )
        try:
            facts_result = ontology_port.sparql_query(facts_query)
        except Exception as exc:
            logger.warning(
                "SPARQL facts query failed for %s: %s", subj, exc,
            )
            chain.append({"subject": subj, "facts": []})
            continue

        facts = [
            {
                "subject": subj,
                "predicate": b.get("p", ""),
                "object": b.get("o", ""),
            }
            for b in facts_result.get("results", [])
        ]
        chain.append({"subject": subj, "facts": facts})

    return chain
