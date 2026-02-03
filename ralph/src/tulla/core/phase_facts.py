"""Phase fact persistence: dataclasses, persister, and upstream collection.

Provides :class:`PersistResult` — the return type used by the persister to
communicate what happened during a persist-validate-rollback cycle — and
:class:`PhaseFactPersister` which orchestrates the extraction, storage,
validation, and optional rollback of intent-annotated phase output fields.

Also provides :func:`collect_upstream_facts` for iterative traversal of
prior-phase facts (arch:adr-67-4).

Architecture decisions: arch:adr-67-1, arch:adr-67-2, arch:adr-67-4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from tulla.core.intent import extract_intent_fields
from tulla.core.phase import PhaseResult
from tulla.ports.ontology import OntologyPort

logger = logging.getLogger(__name__)


@dataclass
class PersistResult:
    """Outcome of persisting phase facts to the ontology store.

    Attributes:
        stored_count: Number of facts successfully stored.
        validation_passed: None if no SHACL shape exists for the phase,
            True if validation succeeded, False if it failed.
        validation_errors: SHACL violation messages; empty when
            validation passed or no shape exists.
        rolled_back: True if stored facts were rolled back because
            validation failed.
    """

    stored_count: int = 0
    validation_passed: bool | None = None
    validation_errors: list[str] = field(default_factory=list)
    rolled_back: bool = False


class PhaseFactPersister:
    """Persists intent-annotated phase output fields as ontology facts.

    Follows the idempotent-write pattern established by P6 hydration:
    ``forget_by_context`` clears stale facts before storing fresh ones,
    making the operation safe for pipeline resume/rerun.

    Parameters:
        ontology: The :class:`OntologyPort` used for all store/forget/validate
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
        """Persist intent fields from a phase result into the ontology.

        Steps:
            1. Extract intent fields — return no-op if empty.
            2. Compute context and subject URI.
            3. Idempotent cleanup via ``forget_by_context``.
            4. Store each intent field as a ``phase:preserves-{name}`` fact.
            5. Store ``phase:producedBy`` linking subject to the phase.
            6. Store ``phase:forRequirement`` linking subject to the idea.
            7. If predecessor given, store ``trace:tracesTo``.
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

        # (2) Compute context and subject URI
        context = f"phase-idea-{idea_id}-{phase_id}"
        subject = f"phase:{idea_id}-{phase_id}"

        # (3) Idempotent cleanup
        cleared = self._ontology.forget_by_context(context)
        if cleared:
            logger.info(
                "Cleared %d existing facts from context %s",
                cleared,
                context,
            )

        stored = 0
        errors = 0

        # (4) Store each intent field
        for field_name, value in intent_fields.items():
            predicate = f"phase:preserves-{field_name}"
            try:
                self._ontology.store_fact(
                    subject, predicate, str(value), context=context,
                )
                stored += 1
            except Exception as exc:
                errors += 1
                logger.debug(
                    "store_fact failed for (%s, %s): %s",
                    subject,
                    predicate,
                    exc,
                )

        # (5) Store phase:producedBy
        try:
            self._ontology.store_fact(
                subject, "phase:producedBy", phase_id, context=context,
            )
            stored += 1
        except Exception as exc:
            errors += 1
            logger.debug("store_fact failed for producedBy: %s", exc)

        # (6) Store phase:forRequirement
        try:
            self._ontology.store_fact(
                subject, "phase:forRequirement", idea_id, context=context,
            )
            stored += 1
        except Exception as exc:
            errors += 1
            logger.debug("store_fact failed for forRequirement: %s", exc)

        # (7) Optional trace:tracesTo predecessor
        if predecessor_phase_id is not None:
            predecessor_subject = f"phase:{idea_id}-{predecessor_phase_id}"
            try:
                self._ontology.store_fact(
                    subject,
                    "trace:tracesTo",
                    predecessor_subject,
                    context=context,
                )
                stored += 1
            except Exception as exc:
                errors += 1
                logger.debug("store_fact failed for tracesTo: %s", exc)

        if errors:
            logger.warning(
                "Phase fact persistence: %d/%d store_fact calls failed "
                "for context %s",
                errors,
                stored + errors,
                context,
            )

        # (8) Optional SHACL validation + rollback
        if shacl_shape_id is not None:
            try:
                result = self._ontology.validate_instance(subject, shacl_shape_id)
            except Exception as exc:
                logger.error(
                    "validate_instance raised for %s shape %s: %s",
                    subject,
                    shacl_shape_id,
                    exc,
                )
                # Treat exception as validation failure — roll back
                self._ontology.forget_by_context(context)
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
                    "SHACL validation failed for %s — rolling back %d facts",
                    subject,
                    stored,
                )
                self._ontology.forget_by_context(context)
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
    """Collect facts from all phases preceding *current_phase_id*.

    Iterates over *phase_sequence* up to (but not including)
    *current_phase_id*, calling ``recall_facts`` for each prior phase
    using the context ``phase-idea-{idea_id}-{pid}``.

    Returns a flat list of recalled fact dicts ordered by phase sequence.
    If *current_phase_id* is the first phase or is not found in the
    sequence, an empty list is returned.

    Exceptions raised by ``recall_facts`` for any individual phase are
    logged as warnings and skipped so that one failing phase does not
    block downstream collection (arch:adr-67-4).
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

    all_facts: list[dict[str, Any]] = []
    for pid in phase_sequence[:current_idx]:
        context = f"phase-idea-{idea_id}-{pid}"
        try:
            result = ontology_port.recall_facts(context=context)
        except Exception as exc:
            logger.warning(
                "recall_facts failed for context %s: %s", context, exc,
            )
            continue
        facts = result.get("facts", [])
        all_facts.extend(facts)

    return all_facts
