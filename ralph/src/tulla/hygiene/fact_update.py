"""Safe fact-update utilities enforcing forget-before-store ordering.

Fixes the store-before-forget ordering bug in main loop prompts where
updating a fact (e.g., changing prd:status from Pending to Complete)
could temporarily create duplicate triples if store_fact is called
before forget_fact.

The correct sequence is:
    1. forget_fact(old_fact_id)   -- remove the stale triple first
    2. store_fact(new_value)      -- then write the new triple

This module provides:
    - FactUpdate: a declarative description of a fact transition
    - apply_fact_update(): executes a single update in correct order
    - apply_fact_updates(): batch-applies multiple updates
    - validate_fact_update(): pre-checks that an update is well-formed
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Protocol, Sequence

logger = logging.getLogger(__name__)


class FactStore(Protocol):
    """Protocol describing the fact-storage interface.

    Any backend that provides store_fact and forget_fact with
    compatible signatures satisfies this protocol.
    """

    def store_fact(
        self,
        subject: str,
        predicate: str,
        object: str,
        context: str | None = None,
        confidence: float = 1.0,
    ) -> dict[str, Any]:
        """Store a new fact, returning the created fact record."""
        ...

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        """Remove a fact by its ID, returning the operation result."""
        ...


@dataclass(frozen=True)
class FactUpdate:
    """Declarative description of a single fact transition.

    Captures both the old fact to remove and the new value to store,
    ensuring all information needed for a safe update is co-located.

    Attributes:
        old_fact_id: The fact_id of the existing triple to forget.
        subject: The subject of the triple (unchanged across the update).
        predicate: The predicate of the triple (unchanged across the update).
        new_object: The new object value to store.
        context: Optional context tag for the new fact.
        confidence: Confidence score for the new fact (default 1.0).
    """

    old_fact_id: str
    subject: str
    predicate: str
    new_object: str
    context: str | None = None
    confidence: float = 1.0


class FactUpdateError(Exception):
    """Raised when a fact update operation fails."""

    def __init__(self, message: str, update: FactUpdate, phase: str) -> None:
        self.update = update
        self.phase = phase
        super().__init__(message)


def validate_fact_update(update: FactUpdate) -> list[str]:
    """Validate that a FactUpdate is well-formed before execution.

    Args:
        update: The fact update to validate.

    Returns:
        A list of validation error messages. Empty list means valid.
    """
    errors: list[str] = []

    if not update.old_fact_id or not update.old_fact_id.strip():
        errors.append("old_fact_id must be a non-empty string")

    if not update.subject or not update.subject.strip():
        errors.append("subject must be a non-empty string")

    if not update.predicate or not update.predicate.strip():
        errors.append("predicate must be a non-empty string")

    if not update.new_object or not update.new_object.strip():
        errors.append("new_object must be a non-empty string")

    if not (0.0 <= update.confidence <= 1.0):
        errors.append(
            f"confidence must be between 0.0 and 1.0, got {update.confidence}"
        )

    return errors


def apply_fact_update(
    update: FactUpdate,
    *,
    store_fn: Callable[..., dict[str, Any]],
    forget_fn: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    """Apply a single fact update using forget-before-store ordering.

    This is the core fix for the store-before-forget ordering bug.
    The old fact is removed FIRST, then the new fact is stored.

    Args:
        update: The declarative fact transition to apply.
        store_fn: Callable matching the FactStore.store_fact signature.
        forget_fn: Callable matching the FactStore.forget_fact signature.

    Returns:
        The result dict from the store_fn call (the newly created fact).

    Raises:
        FactUpdateError: If validation fails or either operation errors.
    """
    # Phase 0: Validate
    errors = validate_fact_update(update)
    if errors:
        raise FactUpdateError(
            f"Invalid fact update: {'; '.join(errors)}",
            update=update,
            phase="validation",
        )

    # Phase 1: FORGET the old fact first (critical ordering fix)
    logger.debug(
        "Forgetting old fact %s for %s.%s",
        update.old_fact_id,
        update.subject,
        update.predicate,
    )
    try:
        forget_fn(update.old_fact_id)
    except Exception as exc:
        raise FactUpdateError(
            f"Failed to forget old fact {update.old_fact_id}: {exc}",
            update=update,
            phase="forget",
        ) from exc

    # Phase 2: STORE the new fact (after old is gone)
    logger.debug(
        "Storing new fact %s.%s = %s",
        update.subject,
        update.predicate,
        update.new_object,
    )
    store_kwargs: dict[str, Any] = {
        "subject": update.subject,
        "predicate": update.predicate,
        "object": update.new_object,
    }
    if update.context is not None:
        store_kwargs["context"] = update.context
    if update.confidence != 1.0:
        store_kwargs["confidence"] = update.confidence

    try:
        result = store_fn(**store_kwargs)
    except Exception as exc:
        raise FactUpdateError(
            f"Failed to store new fact for {update.subject}.{update.predicate}: {exc}",
            update=update,
            phase="store",
        ) from exc

    logger.info(
        "Updated %s.%s: forgot %s, stored new value '%s'",
        update.subject,
        update.predicate,
        update.old_fact_id,
        update.new_object,
    )

    return result


def apply_fact_updates(
    updates: Sequence[FactUpdate],
    *,
    store_fn: Callable[..., dict[str, Any]],
    forget_fn: Callable[[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply multiple fact updates in sequence, each in correct order.

    Each update individually follows forget-before-store ordering.
    If any update fails, previously completed updates are NOT rolled back.

    Args:
        updates: Sequence of FactUpdate transitions to apply.
        store_fn: Callable matching the FactStore.store_fact signature.
        forget_fn: Callable matching the FactStore.forget_fact signature.

    Returns:
        List of result dicts from each store_fn call, in order.

    Raises:
        FactUpdateError: If any individual update fails.
    """
    if not updates:
        return []

    # Pre-validate all updates before making any changes
    all_errors: list[tuple[int, list[str]]] = []
    for i, update in enumerate(updates):
        errors = validate_fact_update(update)
        if errors:
            all_errors.append((i, errors))

    if all_errors:
        error_details = "; ".join(
            f"update[{i}]: {', '.join(errs)}" for i, errs in all_errors
        )
        raise FactUpdateError(
            f"Batch validation failed: {error_details}",
            update=updates[all_errors[0][0]],
            phase="validation",
        )

    # Apply updates sequentially
    results: list[dict[str, Any]] = []
    for i, update in enumerate(updates):
        logger.debug("Applying batch update %d/%d", i + 1, len(updates))
        result = apply_fact_update(
            update, store_fn=store_fn, forget_fn=forget_fn
        )
        results.append(result)

    logger.info("Applied %d fact updates successfully", len(results))
    return results
