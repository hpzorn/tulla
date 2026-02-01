"""Tests for the fact_update module — forget-before-store ordering fix."""

from __future__ import annotations

import pytest

from ralph.hygiene.fact_update import (
    FactUpdate,
    FactUpdateError,
    apply_fact_update,
    apply_fact_updates,
    validate_fact_update,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class CallRecorder:
    """Records calls to mock store/forget functions in order."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | str]] = []

    def store(self, **kwargs) -> dict:
        self.calls.append(("store", kwargs))
        return {"fact_id": f"new-{len(self.calls)}"}

    def forget(self, fact_id: str) -> dict:
        self.calls.append(("forget", fact_id))
        return {"status": "forgotten"}


def make_update(**overrides) -> FactUpdate:
    """Create a FactUpdate with sensible defaults."""
    defaults = {
        "old_fact_id": "abc123",
        "subject": "prd:req-1",
        "predicate": "prd:status",
        "new_object": "prd:Complete",
        "context": "prd-test",
        "confidence": 1.0,
    }
    defaults.update(overrides)
    return FactUpdate(**defaults)


# ---------------------------------------------------------------------------
# FactUpdate dataclass tests
# ---------------------------------------------------------------------------

class TestFactUpdate:
    """Tests for the FactUpdate frozen dataclass."""

    def test_create_with_all_fields(self) -> None:
        update = FactUpdate(
            old_fact_id="f1",
            subject="s",
            predicate="p",
            new_object="o",
            context="ctx",
            confidence=0.9,
        )
        assert update.old_fact_id == "f1"
        assert update.subject == "s"
        assert update.predicate == "p"
        assert update.new_object == "o"
        assert update.context == "ctx"
        assert update.confidence == 0.9

    def test_create_with_defaults(self) -> None:
        update = FactUpdate(
            old_fact_id="f1",
            subject="s",
            predicate="p",
            new_object="o",
        )
        assert update.context is None
        assert update.confidence == 1.0

    def test_frozen(self) -> None:
        update = make_update()
        with pytest.raises(AttributeError):
            update.subject = "changed"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = make_update(old_fact_id="x")
        b = make_update(old_fact_id="x")
        assert a == b

    def test_inequality(self) -> None:
        a = make_update(old_fact_id="x")
        b = make_update(old_fact_id="y")
        assert a != b


# ---------------------------------------------------------------------------
# validate_fact_update tests
# ---------------------------------------------------------------------------

class TestValidateFactUpdate:
    """Tests for the validate_fact_update function."""

    def test_valid_update_no_errors(self) -> None:
        assert validate_fact_update(make_update()) == []

    def test_empty_old_fact_id(self) -> None:
        errors = validate_fact_update(make_update(old_fact_id=""))
        assert len(errors) == 1
        assert "old_fact_id" in errors[0]

    def test_whitespace_only_old_fact_id(self) -> None:
        errors = validate_fact_update(make_update(old_fact_id="   "))
        assert len(errors) == 1
        assert "old_fact_id" in errors[0]

    def test_empty_subject(self) -> None:
        errors = validate_fact_update(make_update(subject=""))
        assert any("subject" in e for e in errors)

    def test_empty_predicate(self) -> None:
        errors = validate_fact_update(make_update(predicate=""))
        assert any("predicate" in e for e in errors)

    def test_empty_new_object(self) -> None:
        errors = validate_fact_update(make_update(new_object=""))
        assert any("new_object" in e for e in errors)

    def test_confidence_below_zero(self) -> None:
        errors = validate_fact_update(make_update(confidence=-0.1))
        assert any("confidence" in e for e in errors)

    def test_confidence_above_one(self) -> None:
        errors = validate_fact_update(make_update(confidence=1.5))
        assert any("confidence" in e for e in errors)

    def test_confidence_boundary_zero(self) -> None:
        assert validate_fact_update(make_update(confidence=0.0)) == []

    def test_confidence_boundary_one(self) -> None:
        assert validate_fact_update(make_update(confidence=1.0)) == []

    def test_multiple_errors_reported(self) -> None:
        errors = validate_fact_update(
            make_update(old_fact_id="", subject="", predicate="")
        )
        assert len(errors) >= 3


# ---------------------------------------------------------------------------
# apply_fact_update tests — ordering guarantee
# ---------------------------------------------------------------------------

class TestApplyFactUpdate:
    """Tests for the apply_fact_update function.

    The critical property: forget is always called BEFORE store.
    """

    def test_forget_before_store_ordering(self) -> None:
        """The core bug fix: forget must come before store."""
        recorder = CallRecorder()
        apply_fact_update(
            make_update(),
            store_fn=recorder.store,
            forget_fn=recorder.forget,
        )
        assert len(recorder.calls) == 2
        assert recorder.calls[0][0] == "forget"
        assert recorder.calls[1][0] == "store"

    def test_forget_receives_old_fact_id(self) -> None:
        recorder = CallRecorder()
        apply_fact_update(
            make_update(old_fact_id="deadbeef"),
            store_fn=recorder.store,
            forget_fn=recorder.forget,
        )
        assert recorder.calls[0] == ("forget", "deadbeef")

    def test_store_receives_correct_fields(self) -> None:
        recorder = CallRecorder()
        apply_fact_update(
            make_update(
                subject="prd:req-42",
                predicate="prd:status",
                new_object="prd:Complete",
                context="prd-99",
            ),
            store_fn=recorder.store,
            forget_fn=recorder.forget,
        )
        store_args = recorder.calls[1][1]
        assert store_args["subject"] == "prd:req-42"
        assert store_args["predicate"] == "prd:status"
        assert store_args["object"] == "prd:Complete"
        assert store_args["context"] == "prd-99"

    def test_store_omits_context_when_none(self) -> None:
        recorder = CallRecorder()
        apply_fact_update(
            make_update(context=None),
            store_fn=recorder.store,
            forget_fn=recorder.forget,
        )
        store_args = recorder.calls[1][1]
        assert "context" not in store_args

    def test_store_omits_confidence_when_default(self) -> None:
        recorder = CallRecorder()
        apply_fact_update(
            make_update(confidence=1.0),
            store_fn=recorder.store,
            forget_fn=recorder.forget,
        )
        store_args = recorder.calls[1][1]
        assert "confidence" not in store_args

    def test_store_includes_confidence_when_non_default(self) -> None:
        recorder = CallRecorder()
        apply_fact_update(
            make_update(confidence=0.8),
            store_fn=recorder.store,
            forget_fn=recorder.forget,
        )
        store_args = recorder.calls[1][1]
        assert store_args["confidence"] == 0.8

    def test_returns_store_result(self) -> None:
        recorder = CallRecorder()
        result = apply_fact_update(
            make_update(),
            store_fn=recorder.store,
            forget_fn=recorder.forget,
        )
        assert "fact_id" in result

    def test_validation_error_prevents_execution(self) -> None:
        recorder = CallRecorder()
        with pytest.raises(FactUpdateError) as exc_info:
            apply_fact_update(
                make_update(old_fact_id=""),
                store_fn=recorder.store,
                forget_fn=recorder.forget,
            )
        assert exc_info.value.phase == "validation"
        assert len(recorder.calls) == 0  # Nothing executed

    def test_forget_error_propagates(self) -> None:
        def failing_forget(fid: str) -> dict:
            raise RuntimeError("forget failed")

        recorder = CallRecorder()
        with pytest.raises(FactUpdateError) as exc_info:
            apply_fact_update(
                make_update(),
                store_fn=recorder.store,
                forget_fn=failing_forget,
            )
        assert exc_info.value.phase == "forget"
        # Store should NOT have been called
        assert len(recorder.calls) == 0

    def test_store_error_propagates(self) -> None:
        def failing_store(**kwargs) -> dict:
            raise RuntimeError("store failed")

        calls: list[str] = []

        def tracking_forget(fid: str) -> dict:
            calls.append("forget")
            return {"status": "ok"}

        with pytest.raises(FactUpdateError) as exc_info:
            apply_fact_update(
                make_update(),
                store_fn=failing_store,
                forget_fn=tracking_forget,
            )
        assert exc_info.value.phase == "store"
        # Forget WAS called (correct order), store failed after
        assert calls == ["forget"]


# ---------------------------------------------------------------------------
# FactUpdateError tests
# ---------------------------------------------------------------------------

class TestFactUpdateError:
    """Tests for the FactUpdateError exception."""

    def test_has_update_and_phase(self) -> None:
        update = make_update()
        err = FactUpdateError("msg", update=update, phase="forget")
        assert err.update is update
        assert err.phase == "forget"
        assert "msg" in str(err)

    def test_is_exception(self) -> None:
        assert issubclass(FactUpdateError, Exception)


# ---------------------------------------------------------------------------
# apply_fact_updates batch tests
# ---------------------------------------------------------------------------

class TestApplyFactUpdates:
    """Tests for the batch apply_fact_updates function."""

    def test_empty_list_returns_empty(self) -> None:
        recorder = CallRecorder()
        results = apply_fact_updates(
            [], store_fn=recorder.store, forget_fn=recorder.forget
        )
        assert results == []
        assert len(recorder.calls) == 0

    def test_single_update(self) -> None:
        recorder = CallRecorder()
        results = apply_fact_updates(
            [make_update()],
            store_fn=recorder.store,
            forget_fn=recorder.forget,
        )
        assert len(results) == 1
        assert recorder.calls[0][0] == "forget"
        assert recorder.calls[1][0] == "store"

    def test_multiple_updates_ordering(self) -> None:
        """Each update should follow forget-then-store ordering."""
        recorder = CallRecorder()
        updates = [
            make_update(old_fact_id="old1", subject="s1"),
            make_update(old_fact_id="old2", subject="s2"),
            make_update(old_fact_id="old3", subject="s3"),
        ]
        results = apply_fact_updates(
            updates, store_fn=recorder.store, forget_fn=recorder.forget
        )
        assert len(results) == 3
        # Each pair should be (forget, store)
        for i in range(3):
            assert recorder.calls[i * 2][0] == "forget"
            assert recorder.calls[i * 2 + 1][0] == "store"

    def test_batch_validation_fails_fast(self) -> None:
        """All updates are validated before any are executed."""
        recorder = CallRecorder()
        updates = [
            make_update(),  # valid
            make_update(old_fact_id=""),  # invalid
        ]
        with pytest.raises(FactUpdateError) as exc_info:
            apply_fact_updates(
                updates, store_fn=recorder.store, forget_fn=recorder.forget
            )
        assert exc_info.value.phase == "validation"
        assert len(recorder.calls) == 0  # Nothing executed

    def test_returns_all_results(self) -> None:
        recorder = CallRecorder()
        updates = [
            make_update(old_fact_id="a", subject="s1"),
            make_update(old_fact_id="b", subject="s2"),
        ]
        results = apply_fact_updates(
            updates, store_fn=recorder.store, forget_fn=recorder.forget
        )
        assert len(results) == 2
        assert all("fact_id" in r for r in results)

    def test_mid_batch_failure_stops(self) -> None:
        """If one update fails, subsequent updates are not attempted."""
        call_count = 0

        def counting_forget(fid: str) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("second forget fails")
            return {"status": "ok"}

        recorder = CallRecorder()
        updates = [
            make_update(old_fact_id="a"),
            make_update(old_fact_id="b"),
            make_update(old_fact_id="c"),
        ]
        with pytest.raises(FactUpdateError):
            apply_fact_updates(
                updates, store_fn=recorder.store, forget_fn=counting_forget
            )
        # First update completed (forget + store), second forget failed
        # Third update never started
        assert call_count == 2
