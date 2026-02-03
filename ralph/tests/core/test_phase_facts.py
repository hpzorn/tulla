"""Tests for tulla.core.phase_facts — PersistResult and PhaseFactPersister."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call

import pytest
from pydantic import BaseModel, Field

from tulla.core.intent import IntentField
from tulla.core.phase import PhaseResult, PhaseStatus
from tulla.core.phase_facts import PersistResult, PhaseFactPersister, collect_upstream_facts, traverse_chain
from tulla.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class _TwoIntentModel(BaseModel):
    """Model with 2 intent fields and 1 plain field."""

    goal: str = IntentField(default="g", description="The goal")
    scope: str = IntentField(default="s", description="The scope")
    revision: int = Field(default=0)


class _NoIntentModel(BaseModel):
    """Model with zero intent fields."""

    name: str = Field(default="anon")
    count: int = Field(default=0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_port() -> MagicMock:
    """Create a mock OntologyPort."""
    port = MagicMock(spec=OntologyPort)
    port.forget_by_context.return_value = 0
    port.store_fact.return_value = {"ok": True}
    port.validate_instance.return_value = {"conforms": True, "violations": []}
    return port


@pytest.fixture()
def port() -> MagicMock:
    return _make_port()


@pytest.fixture()
def persister(port: MagicMock) -> PhaseFactPersister:
    return PhaseFactPersister(port)


# ===================================================================
# PersistResult dataclass
# ===================================================================


class TestPersistResult:
    """Smoke tests for the PersistResult dataclass."""

    def test_defaults(self) -> None:
        r = PersistResult()
        assert r.stored_count == 0
        assert r.validation_passed is None
        assert r.validation_errors == []
        assert r.rolled_back is False

    def test_custom_values(self) -> None:
        r = PersistResult(
            stored_count=5,
            validation_passed=True,
            validation_errors=["e1"],
            rolled_back=True,
        )
        assert r.stored_count == 5
        assert r.validation_passed is True
        assert r.validation_errors == ["e1"]
        assert r.rolled_back is True


# ===================================================================
# PhaseFactPersister — 2 intent fields happy path
# ===================================================================


class TestPersistTwoIntentFields:
    """Persist a model with 2 intent fields — verify correct store_fact calls."""

    def test_correct_store_fact_count(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """2 intent fields + producedBy + forRequirement = 4 store_fact calls."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(goal="ship it", scope="backend"),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        assert result.stored_count == 4
        assert port.store_fact.call_count == 4

    def test_intent_field_predicates(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """Each intent field becomes a phase:preserves-{name} fact."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(goal="ship it", scope="backend"),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        stored_predicates = [c.args[1] for c in port.store_fact.call_args_list]
        assert "phase:preserves-goal" in stored_predicates
        assert "phase:preserves-scope" in stored_predicates

    def test_produced_by_fact(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        calls = port.store_fact.call_args_list
        produced_by = [c for c in calls if c.args[1] == "phase:producedBy"]
        assert len(produced_by) == 1
        assert produced_by[0].args[0] == "phase:42-d1"
        assert produced_by[0].args[2] == "d1"

    def test_for_requirement_fact(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        calls = port.store_fact.call_args_list
        for_req = [c for c in calls if c.args[1] == "phase:forRequirement"]
        assert len(for_req) == 1
        assert for_req[0].args[0] == "phase:42-d1"
        assert for_req[0].args[2] == "42"

    def test_context_string(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """All facts use context = 'phase-idea-{idea_id}-{phase_id}'."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        for c in port.store_fact.call_args_list:
            assert c.kwargs["context"] == "phase-idea-42-d1"

    def test_subject_uri(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """All facts use subject = 'phase:{idea_id}-{phase_id}'."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        for c in port.store_fact.call_args_list:
            assert c.args[0] == "phase:42-d1"

    def test_forget_by_context_called_before_store(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """Idempotent cleanup: forget_by_context is called before any store_fact."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        port.forget_by_context.assert_called_once_with("phase-idea-42-d1")

    def test_validation_passed_none_without_shape(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """When no SHACL shape, validation_passed is None."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        assert result.validation_passed is None


# ===================================================================
# PhaseFactPersister — no-op for 0 intent fields
# ===================================================================


class TestPersistNoIntentFields:
    """Persist a model with 0 intent fields — confirm no-op."""

    def test_noop_result(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_NoIntentModel(name="test", count=5),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        assert result.stored_count == 0
        assert result.validation_passed is None
        assert result.rolled_back is False

    def test_no_store_calls(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_NoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        port.store_fact.assert_not_called()
        port.forget_by_context.assert_not_called()

    def test_noop_for_none_data(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=None,
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        assert result.stored_count == 0
        port.store_fact.assert_not_called()


# ===================================================================
# PhaseFactPersister — predecessor trace
# ===================================================================


class TestPersistWithPredecessor:
    """Confirm trace:tracesTo fact is stored when predecessor_phase_id is given."""

    def test_traces_to_stored(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d2",
            phase_result=phase_result,
            predecessor_phase_id="d1",
            shacl_shape_id=None,
        )

        # 2 intent + producedBy + forRequirement + tracesTo = 5
        assert result.stored_count == 5
        assert port.store_fact.call_count == 5

        calls = port.store_fact.call_args_list
        trace_calls = [c for c in calls if c.args[1] == "trace:tracesTo"]
        assert len(trace_calls) == 1
        assert trace_calls[0].args[0] == "phase:42-d2"
        assert trace_calls[0].args[2] == "phase:42-d1"

    def test_no_traces_to_without_predecessor(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d2",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        calls = port.store_fact.call_args_list
        trace_calls = [c for c in calls if c.args[1] == "trace:tracesTo"]
        assert len(trace_calls) == 0


# ===================================================================
# PhaseFactPersister — SHACL validation
# ===================================================================


class TestPersistShaclValidation:
    """SHACL validation: pass, fail with rollback."""

    def test_validation_pass(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        port.validate_instance.return_value = {
            "conforms": True,
            "violations": [],
        }
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id="shapes:PhaseOutput",
        )

        assert result.validation_passed is True
        assert result.rolled_back is False
        assert result.validation_errors == []
        port.validate_instance.assert_called_once_with(
            "phase:42-d1", "shapes:PhaseOutput",
        )

    def test_validation_fail_rolls_back(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        port.validate_instance.return_value = {
            "conforms": False,
            "violations": ["missing phase:preserves-goal"],
        }
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id="shapes:PhaseOutput",
        )

        assert result.validation_passed is False
        assert result.rolled_back is True
        assert "missing phase:preserves-goal" in result.validation_errors

        # forget_by_context called twice: idempotent cleanup + rollback
        assert port.forget_by_context.call_count == 2
        rollback_call = port.forget_by_context.call_args_list[1]
        assert rollback_call.args[0] == "phase-idea-42-d1"

    def test_validation_exception_rolls_back(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        port.validate_instance.side_effect = RuntimeError("server down")
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id="shapes:PhaseOutput",
        )

        assert result.validation_passed is False
        assert result.rolled_back is True
        assert "server down" in result.validation_errors[0]
        # forget_by_context called twice: idempotent cleanup + rollback
        assert port.forget_by_context.call_count == 2


# ===================================================================
# PhaseFactPersister — error counter (P6 hydration pattern)
# ===================================================================


class TestPersistErrorCounter:
    """Errors in store_fact are counted, not raised."""

    def test_partial_failures_still_return_result(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        # First call succeeds, second raises, rest succeed
        port.store_fact.side_effect = [
            {"ok": True},  # preserves-goal
            RuntimeError("transient"),  # preserves-scope
            {"ok": True},  # producedBy
            {"ok": True},  # forRequirement
        ]
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        # 3 succeeded out of 4 attempts
        assert result.stored_count == 3

    def test_string_representation_of_values(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """Intent field values are stored as str(value)."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(goal="my goal", scope="full"),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        intent_calls = [
            c for c in port.store_fact.call_args_list
            if c.args[1].startswith("phase:preserves-")
        ]
        values = {c.args[1]: c.args[2] for c in intent_calls}
        assert values["phase:preserves-goal"] == "my goal"
        assert values["phase:preserves-scope"] == "full"


# ===================================================================
# collect_upstream_facts
# ===================================================================


class TestCollectUpstreamFacts:
    """Tests for the collect_upstream_facts standalone function."""

    PHASES = ["d1", "d2", "d3", "d4"]

    def _make_recall(self, mapping: dict[str, list[dict[str, Any]]]):
        """Return a side_effect callable that returns facts keyed by context."""
        def _recall(*, subject=None, predicate=None, context=None, limit=100):
            facts = mapping.get(context, [])
            return {"facts": facts}
        return _recall

    def test_calls_recall_for_each_prior_phase(self, port: MagicMock) -> None:
        """recall_facts is called once per prior phase in sequence order."""
        port.recall_facts.side_effect = self._make_recall({})

        collect_upstream_facts(port, "42", self.PHASES, "d3")

        assert port.recall_facts.call_count == 2
        expected = [
            call(context="phase-idea-42-d1"),
            call(context="phase-idea-42-d2"),
        ]
        assert port.recall_facts.call_args_list == expected

    def test_skips_current_and_subsequent_phases(self, port: MagicMock) -> None:
        """Current phase and all phases after it are not recalled."""
        port.recall_facts.side_effect = self._make_recall({})

        collect_upstream_facts(port, "42", self.PHASES, "d2")

        assert port.recall_facts.call_count == 1
        port.recall_facts.assert_called_once_with(context="phase-idea-42-d1")

    def test_returns_flat_list_ordered_by_sequence(self, port: MagicMock) -> None:
        """Facts from each phase are concatenated in sequence order."""
        facts_d1 = [{"id": "f1", "subject": "s1"}]
        facts_d2 = [{"id": "f2", "subject": "s2"}, {"id": "f3", "subject": "s3"}]
        port.recall_facts.side_effect = self._make_recall({
            "phase-idea-42-d1": facts_d1,
            "phase-idea-42-d2": facts_d2,
        })

        result = collect_upstream_facts(port, "42", self.PHASES, "d3")

        assert result == [
            {"id": "f1", "subject": "s1"},
            {"id": "f2", "subject": "s2"},
            {"id": "f3", "subject": "s3"},
        ]

    def test_empty_list_for_first_phase(self, port: MagicMock) -> None:
        """If current_phase_id is the first phase, return empty list."""
        result = collect_upstream_facts(port, "42", self.PHASES, "d1")

        assert result == []
        port.recall_facts.assert_not_called()

    def test_empty_list_for_unknown_phase(self, port: MagicMock) -> None:
        """If current_phase_id is not in the sequence, return empty list."""
        result = collect_upstream_facts(port, "42", self.PHASES, "unknown")

        assert result == []
        port.recall_facts.assert_not_called()

    def test_exception_in_recall_logged_and_skipped(self, port: MagicMock) -> None:
        """If recall_facts raises for one phase, skip it and continue."""
        facts_d2 = [{"id": "f2"}]

        def _side_effect(*, subject=None, predicate=None, context=None, limit=100):
            if context == "phase-idea-42-d1":
                raise RuntimeError("server timeout")
            return {"facts": facts_d2}

        port.recall_facts.side_effect = _side_effect

        result = collect_upstream_facts(port, "42", self.PHASES, "d3")

        # d1 failed, d2 succeeded
        assert result == [{"id": "f2"}]
        assert port.recall_facts.call_count == 2

    def test_all_phases_fail_returns_empty(self, port: MagicMock) -> None:
        """If all prior phases fail, return empty list."""
        port.recall_facts.side_effect = RuntimeError("all down")

        result = collect_upstream_facts(port, "42", self.PHASES, "d3")

        assert result == []
        assert port.recall_facts.call_count == 2

    def test_empty_sequence(self, port: MagicMock) -> None:
        """Empty phase_sequence returns empty list."""
        result = collect_upstream_facts(port, "42", [], "d1")

        assert result == []
        port.recall_facts.assert_not_called()


# ===================================================================
# traverse_chain
# ===================================================================


class TestTraverseChain:
    """Tests for the traverse_chain function (link-following traversal)."""

    def _make_recall(
        self,
        all_facts: dict[str, list[dict[str, Any]]],
        trace_links: dict[str, str],
    ):
        """Return a side_effect callable for recall_facts.

        Args:
            all_facts: Maps subject URI -> list of fact dicts for that subject.
            trace_links: Maps subject URI -> the target subject of its tracesTo link.
        """
        def _recall(
            *,
            subject: str | None = None,
            predicate: str | None = None,
            context: str | None = None,
            limit: int = 100,
        ) -> dict[str, Any]:
            if predicate == "trace:tracesTo":
                target = trace_links.get(subject or "")
                if target:
                    return {"facts": [{"subject": subject, "predicate": "trace:tracesTo", "object": target}]}
                return {"facts": []}
            # General recall — return all facts for this subject
            facts = all_facts.get(subject or "", [])
            return {"facts": facts}

        return _recall

    def test_three_hop_chain(self, port: MagicMock) -> None:
        """3-hop chain: d3 -> d2 -> d1. Returned in reverse chronological order."""
        all_facts = {
            "phase:42-d3": [{"id": "f3", "subject": "phase:42-d3", "predicate": "phase:preserves-scope", "object": "full"}],
            "phase:42-d2": [{"id": "f2", "subject": "phase:42-d2", "predicate": "phase:preserves-goal", "object": "ship"}],
            "phase:42-d1": [{"id": "f1", "subject": "phase:42-d1", "predicate": "phase:preserves-goal", "object": "plan"}],
        }
        trace_links = {
            "phase:42-d3": "phase:42-d2",
            "phase:42-d2": "phase:42-d1",
            # d1 has no tracesTo — it's the origin
        }
        port.recall_facts.side_effect = self._make_recall(all_facts, trace_links)

        result = traverse_chain(port, "42", "d3")

        assert len(result) == 3
        # Reverse chronological: d3 first, d1 last
        assert result[0]["subject"] == "phase:42-d3"
        assert result[0]["facts"] == all_facts["phase:42-d3"]
        assert result[1]["subject"] == "phase:42-d2"
        assert result[1]["facts"] == all_facts["phase:42-d2"]
        assert result[2]["subject"] == "phase:42-d1"
        assert result[2]["facts"] == all_facts["phase:42-d1"]

    def test_terminates_at_origin(self, port: MagicMock) -> None:
        """Chain terminates when a subject has no tracesTo link (the origin)."""
        all_facts = {
            "phase:42-d1": [{"id": "f1"}],
        }
        trace_links: dict[str, str] = {}  # d1 is the origin
        port.recall_facts.side_effect = self._make_recall(all_facts, trace_links)

        result = traverse_chain(port, "42", "d1")

        assert len(result) == 1
        assert result[0]["subject"] == "phase:42-d1"
        assert result[0]["facts"] == [{"id": "f1"}]

    def test_max_depth_guard(self, port: MagicMock) -> None:
        """Max-depth guard prevents infinite loops from cyclic tracesTo links."""
        # Create a cycle: d1 -> d2 -> d1
        all_facts = {
            "phase:42-d1": [{"id": "f1"}],
            "phase:42-d2": [{"id": "f2"}],
        }
        trace_links = {
            "phase:42-d1": "phase:42-d2",
            "phase:42-d2": "phase:42-d1",  # cycle!
        }
        port.recall_facts.side_effect = self._make_recall(all_facts, trace_links)

        result = traverse_chain(port, "42", "d1", max_depth=5)

        # Should stop at cycle detection, not loop forever
        assert len(result) == 2
        subjects = [r["subject"] for r in result]
        assert subjects == ["phase:42-d1", "phase:42-d2"]

    def test_max_depth_limits_long_chain(self, port: MagicMock) -> None:
        """Max-depth caps traversal even for legitimate long chains."""
        # Build a 10-hop chain but set max_depth=3
        all_facts = {f"phase:42-d{i}": [{"id": f"f{i}"}] for i in range(1, 11)}
        trace_links = {f"phase:42-d{i}": f"phase:42-d{i - 1}" for i in range(2, 11)}
        port.recall_facts.side_effect = self._make_recall(all_facts, trace_links)

        result = traverse_chain(port, "42", "d10", max_depth=3)

        assert len(result) == 3
        assert result[0]["subject"] == "phase:42-d10"
        assert result[1]["subject"] == "phase:42-d9"
        assert result[2]["subject"] == "phase:42-d8"

    def test_recall_exception_stops_traversal(self, port: MagicMock) -> None:
        """If recall_facts raises, traversal stops at that point."""
        call_count = 0

        def _failing_recall(
            *, subject=None, predicate=None, context=None, limit=100,
        ):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"facts": [{"id": "f1"}]}
            raise RuntimeError("server down")

        port.recall_facts.side_effect = _failing_recall

        result = traverse_chain(port, "42", "d2")

        # Only first subject collected before failure
        assert len(result) == 1
        assert result[0]["subject"] == "phase:42-d2"

    def test_empty_facts_still_included(self, port: MagicMock) -> None:
        """A phase with no facts still appears in the chain."""
        all_facts = {
            "phase:42-d2": [],  # no facts but valid node
            "phase:42-d1": [{"id": "f1"}],
        }
        trace_links = {
            "phase:42-d2": "phase:42-d1",
        }
        port.recall_facts.side_effect = self._make_recall(all_facts, trace_links)

        result = traverse_chain(port, "42", "d2")

        assert len(result) == 2
        assert result[0] == {"subject": "phase:42-d2", "facts": []}
        assert result[1] == {"subject": "phase:42-d1", "facts": [{"id": "f1"}]}

    def test_default_max_depth_is_20(self, port: MagicMock) -> None:
        """Default max_depth is 20."""
        from tulla.core.phase_facts import _TRAVERSE_MAX_DEPTH

        assert _TRAVERSE_MAX_DEPTH == 20
