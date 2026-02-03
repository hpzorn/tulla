"""Dataclasses for phase fact persistence results.

Provides the return type used by the persister to communicate what
happened during a persist-validate-rollback cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
