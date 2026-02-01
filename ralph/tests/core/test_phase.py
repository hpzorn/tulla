"""Tests for ralph.core.phase module."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from ralph.core.phase import (
    ParseError,
    Phase,
    PhaseContext,
    PhaseResult,
    PhaseStatus,
)


# ---------------------------------------------------------------------------
# Helpers – concrete Phase subclass for testing
# ---------------------------------------------------------------------------


class _EchoPhase(Phase[str]):
    """Trivial phase that echoes its raw output through parse_output."""

    def build_prompt(self, ctx: PhaseContext) -> str:
        return "echo prompt"

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return []

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        return "raw-output"

    def parse_output(self, ctx: PhaseContext, raw: Any) -> str:
        return str(raw)


class _FailingClaudePhase(_EchoPhase):
    """Phase whose run_claude always raises."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        raise RuntimeError("Claude blew up")


class _TimeoutPhase(_EchoPhase):
    """Phase whose run_claude raises TimeoutError."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        raise TimeoutError("took too long")


class _ParseFailPhase(_EchoPhase):
    """Phase whose parse_output raises ParseError with context."""

    def parse_output(self, ctx: PhaseContext, raw: Any) -> str:
        raise ParseError(
            "bad json",
            raw_output=raw,
            context={"line": 42, "token": "???"},
        )


class _InputValidationFailPhase(_EchoPhase):
    """Phase whose validate_input raises ValueError."""

    def validate_input(self, ctx: PhaseContext) -> None:
        raise ValueError("idea_id must not be empty")


class _OutputValidationFailPhase(_EchoPhase):
    """Phase whose validate_output raises ValueError."""

    def validate_output(self, ctx: PhaseContext, parsed: str) -> None:
        raise ValueError("output too short")


@pytest.fixture()
def ctx(tmp_path: Path) -> PhaseContext:
    """Standard PhaseContext for tests."""
    return PhaseContext(
        idea_id="idea-99",
        work_dir=tmp_path,
        config={"key": "value"},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test"),
    )


# ===================================================================
# PhaseResult.to_dict() round-trip
# ===================================================================


class TestPhaseResultRoundTrip:
    """PhaseResult.to_dict() / from_dict() round-trip tests."""

    def test_success_round_trip(self) -> None:
        original = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data={"items": [1, 2, 3]},
            error=None,
            duration_s=1.23,
            metadata={"attempt": 1},
        )
        d = original.to_dict()
        restored = PhaseResult.from_dict(d)

        assert restored.status == original.status
        assert restored.data == original.data
        assert restored.error == original.error
        assert restored.duration_s == pytest.approx(original.duration_s)
        assert restored.metadata == original.metadata

    def test_failure_round_trip(self) -> None:
        original = PhaseResult(
            status=PhaseStatus.FAILURE,
            data=None,
            error="something broke",
            duration_s=0.5,
        )
        d = original.to_dict()
        restored = PhaseResult.from_dict(d)

        assert restored.status is PhaseStatus.FAILURE
        assert restored.error == "something broke"
        assert restored.data is None

    def test_timeout_round_trip(self) -> None:
        original = PhaseResult(
            status=PhaseStatus.TIMEOUT,
            error="timed out",
            duration_s=30.0,
        )
        d = original.to_dict()
        restored = PhaseResult.from_dict(d)

        assert restored.status is PhaseStatus.TIMEOUT

    def test_to_dict_status_is_string(self) -> None:
        """to_dict() must serialize status as a plain string, not an enum."""
        result = PhaseResult(status=PhaseStatus.SUCCESS, data="ok")
        d = result.to_dict()
        assert isinstance(d["status"], str)
        assert d["status"] == "SUCCESS"


# ===================================================================
# PhaseStatus serialization
# ===================================================================


class TestPhaseStatusSerialization:
    """PhaseStatus enum string conversion tests."""

    def test_str_returns_value(self) -> None:
        assert str(PhaseStatus.SUCCESS) == "SUCCESS"
        assert str(PhaseStatus.FAILURE) == "FAILURE"
        assert str(PhaseStatus.TIMEOUT) == "TIMEOUT"

    def test_value_round_trip(self) -> None:
        for member in PhaseStatus:
            assert PhaseStatus(member.value) is member

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            PhaseStatus("INVALID")


# ===================================================================
# Phase.execute() – success path
# ===================================================================


class TestPhaseExecuteSuccess:
    """Phase.execute() happy-path tests."""

    def test_returns_success_with_data(self, ctx: PhaseContext) -> None:
        result = _EchoPhase().execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data == "raw-output"
        assert result.error is None
        assert result.duration_s > 0

    def test_duration_is_positive(self, ctx: PhaseContext) -> None:
        result = _EchoPhase().execute(ctx)
        assert result.duration_s >= 0


# ===================================================================
# Phase.execute() – failure paths
# ===================================================================


class TestPhaseExecuteFailure:
    """Phase.execute() failure-path tests."""

    def test_run_claude_failure(self, ctx: PhaseContext) -> None:
        result = _FailingClaudePhase().execute(ctx)

        assert result.status is PhaseStatus.FAILURE
        assert "Claude blew up" in (result.error or "")
        assert result.data is None

    def test_input_validation_failure(self, ctx: PhaseContext) -> None:
        result = _InputValidationFailPhase().execute(ctx)

        assert result.status is PhaseStatus.FAILURE
        assert "Input validation failed" in (result.error or "")

    def test_output_validation_failure(self, ctx: PhaseContext) -> None:
        result = _OutputValidationFailPhase().execute(ctx)

        assert result.status is PhaseStatus.FAILURE
        assert "Output validation failed" in (result.error or "")

    def test_parse_error_preserves_context(self, ctx: PhaseContext) -> None:
        result = _ParseFailPhase().execute(ctx)

        assert result.status is PhaseStatus.FAILURE
        assert "Output parsing failed" in (result.error or "")
        assert result.metadata.get("parse_context") == {
            "line": 42,
            "token": "???",
        }


# ===================================================================
# Phase.execute() – timeout path
# ===================================================================


class TestPhaseExecuteTimeout:
    """Phase.execute() timeout-path tests."""

    def test_timeout_returns_timeout_status(self, ctx: PhaseContext) -> None:
        result = _TimeoutPhase().execute(ctx)

        assert result.status is PhaseStatus.TIMEOUT
        assert "timed out" in (result.error or "")
        assert result.data is None


# ===================================================================
# ParseError captures context
# ===================================================================


class TestParseError:
    """ParseError exception tests."""

    def test_message_and_raw_output(self) -> None:
        err = ParseError("bad data", raw_output='{"broken')
        assert str(err) == "bad data"
        assert err.raw_output == '{"broken'

    def test_context_dict(self) -> None:
        err = ParseError(
            "parse fail",
            raw_output=None,
            context={"line": 10, "col": 5},
        )
        assert err.context == {"line": 10, "col": 5}

    def test_default_context_is_empty(self) -> None:
        err = ParseError("oops")
        assert err.context == {}
        assert err.raw_output is None

    def test_is_exception(self) -> None:
        with pytest.raises(ParseError, match="kaboom"):
            raise ParseError("kaboom", context={"reason": "test"})
