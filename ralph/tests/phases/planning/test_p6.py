"""Tests for ralph.phases.planning.p6 -- P6Phase (hygiene gate integration)."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import pytest

from ralph.core.phase import PhaseContext, PhaseStatus
from ralph.hygiene.preflight import HygieneReport, StaleFile
from ralph.phases.planning.models import P6Output
from ralph.phases.planning.p6 import P6Phase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx(tmp_path: Path) -> PhaseContext:
    """Standard PhaseContext pointing at a temporary work directory."""
    return PhaseContext(
        idea_id="idea-42",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.p6"),
    )


@pytest.fixture()
def phase() -> P6Phase:
    """A plain P6Phase instance with default (--clean) argv."""
    return P6Phase()


# ===================================================================
# Construction and defaults
# ===================================================================


class TestConstruction:
    """P6Phase construction and attribute defaults."""

    def test_default_phase_id(self) -> None:
        p = P6Phase()
        assert p.phase_id == "p6"

    def test_default_timeout(self) -> None:
        p = P6Phase()
        assert p.timeout_s == 60.0

    def test_custom_work_dirs(self, tmp_path: Path) -> None:
        dirs = [tmp_path / "a", tmp_path / "b"]
        p = P6Phase(work_dirs=dirs)
        assert p._work_dirs == dirs

    def test_custom_argv(self) -> None:
        p = P6Phase(argv=["--no-clean", "--extra"])
        assert p._argv == ["--no-clean", "--extra"]

    def test_custom_stale_threshold(self) -> None:
        p = P6Phase(stale_threshold_secs=7200)
        assert p._stale_threshold_secs == 7200


# ===================================================================
# build_prompt returns empty string
# ===================================================================


class TestBuildPrompt:
    """P6Phase.build_prompt() returns empty (no LLM interaction)."""

    def test_returns_empty_string(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert prompt == ""


# ===================================================================
# get_tools returns empty list
# ===================================================================


class TestGetTools:
    """P6Phase.get_tools() returns empty list (no LLM interaction)."""

    def test_returns_empty_list(self, phase: P6Phase, ctx: PhaseContext) -> None:
        tools = phase.get_tools(ctx)
        assert tools == []


# ===================================================================
# get_timeout_seconds
# ===================================================================


class TestGetTimeoutSeconds:
    """P6Phase.get_timeout_seconds() returns the configured timeout."""

    def test_returns_timeout(self, phase: P6Phase) -> None:
        assert phase.get_timeout_seconds() == 60.0


# ===================================================================
# validate_input runs the hygiene gate -- CLEAN mode (default)
# ===================================================================


class TestValidateInputClean:
    """P6Phase.validate_input() with default --clean mode."""

    def test_gate_result_populated(self, ctx: PhaseContext) -> None:
        phase = P6Phase(argv=[])
        phase.validate_input(ctx)
        assert phase._gate_result is not None

    def test_gate_result_mode_is_clean(self, ctx: PhaseContext) -> None:
        phase = P6Phase(argv=["--clean"])
        phase.validate_input(ctx)
        assert phase._gate_result.config.mode.value == "clean"

    def test_gate_result_has_report(self, ctx: PhaseContext) -> None:
        phase = P6Phase(argv=["--clean"])
        phase.validate_input(ctx)
        assert phase._gate_result.report is not None


# ===================================================================
# validate_input -- NO_CLEAN mode
# ===================================================================


class TestValidateInputNoClean:
    """P6Phase.validate_input() with --no-clean mode."""

    def test_gate_result_mode_is_no_clean(self, ctx: PhaseContext) -> None:
        phase = P6Phase(argv=["--no-clean"])
        phase.validate_input(ctx)
        assert phase._gate_result.config.mode.value == "no-clean"

    def test_gate_result_report_is_none(self, ctx: PhaseContext) -> None:
        phase = P6Phase(argv=["--no-clean"])
        phase.validate_input(ctx)
        assert phase._gate_result.report is None


# ===================================================================
# validate_input -- CHECK mode
# ===================================================================


class TestValidateInputCheck:
    """P6Phase.validate_input() with --check mode (captured exit)."""

    def test_gate_result_mode_is_check_or_clean(self, ctx: PhaseContext) -> None:
        # In check mode the gate calls exit_func, which we capture.
        # The gate still returns a GateResult.
        phase = P6Phase(argv=["--check"])
        phase.validate_input(ctx)
        # Gate result is populated even in check mode because we
        # provide a non-exiting exit_func.
        assert phase._gate_result is not None


# ===================================================================
# validate_input passes remaining args
# ===================================================================


class TestValidateInputRemainingArgs:
    """P6Phase.validate_input() preserves non-hygiene args."""

    def test_remaining_args_passed_through(self, ctx: PhaseContext) -> None:
        phase = P6Phase(argv=["--clean", "--rounds", "3"])
        phase.validate_input(ctx)
        assert "--rounds" in phase._gate_result.remaining_args
        assert "3" in phase._gate_result.remaining_args


# ===================================================================
# parse_output -- CLEAN mode
# ===================================================================


class TestParseOutputClean:
    """P6Phase.parse_output() converts gate result to P6Output for clean mode."""

    def test_returns_p6_output_clean(self, ctx: PhaseContext) -> None:
        phase = P6Phase(argv=["--clean"])
        phase.validate_input(ctx)
        result = phase.parse_output(ctx, phase._gate_result)

        assert isinstance(result, P6Output)
        assert result.mode == "clean"
        assert result.was_skipped is False

    def test_clean_empty_dir_not_was_cleaned(self, ctx: PhaseContext) -> None:
        # An empty tmp_path has nothing to clean.
        phase = P6Phase(argv=["--clean"])
        phase.validate_input(ctx)
        result = phase.parse_output(ctx, phase._gate_result)
        assert result.was_cleaned is False  # nothing to actually remove

    def test_clean_with_stale_file(self, ctx: PhaseContext) -> None:
        # Create a stale .lock file older than threshold.
        lock_file = ctx.work_dir / "old.lock"
        lock_file.write_text("stale")
        # Backdate the file.
        old_time = time.time() - 7200  # 2 hours ago
        import os
        os.utime(lock_file, (old_time, old_time))

        phase = P6Phase(argv=["--clean"], stale_threshold_secs=3600)
        phase.validate_input(ctx)
        result = phase.parse_output(ctx, phase._gate_result)

        assert result.was_cleaned is True
        assert result.mode == "clean"
        assert not lock_file.exists()  # file was removed


# ===================================================================
# parse_output -- NO_CLEAN mode
# ===================================================================


class TestParseOutputNoClean:
    """P6Phase.parse_output() in no-clean mode marks was_skipped."""

    def test_returns_p6_output_skipped(self, ctx: PhaseContext) -> None:
        phase = P6Phase(argv=["--no-clean"])
        phase.validate_input(ctx)
        result = phase.parse_output(ctx, phase._gate_result)

        assert isinstance(result, P6Output)
        assert result.mode == "no-clean"
        assert result.was_skipped is True
        assert result.was_cleaned is False
        assert result.hygiene_report is None


# ===================================================================
# parse_output -- None gate result (defensive)
# ===================================================================


class TestParseOutputNone:
    """P6Phase.parse_output() with None gate result."""

    def test_returns_unknown_mode(self, phase: P6Phase, ctx: PhaseContext) -> None:
        result = phase.parse_output(ctx, None)
        assert result.mode == "unknown"
        assert result.was_skipped is True
        assert result.was_cleaned is False
        assert result.remaining_args == []


# ===================================================================
# parse_output remaining args
# ===================================================================


class TestParseOutputRemainingArgs:
    """P6Phase.parse_output() passes remaining args through."""

    def test_remaining_args_in_output(self, ctx: PhaseContext) -> None:
        phase = P6Phase(argv=["--clean", "--idea", "42"])
        phase.validate_input(ctx)
        result = phase.parse_output(ctx, phase._gate_result)
        assert "--idea" in result.remaining_args
        assert "42" in result.remaining_args


# ===================================================================
# execute end-to-end -- CLEAN mode
# ===================================================================


class TestExecuteClean:
    """P6Phase.execute() end-to-end in clean mode."""

    def test_execute_clean_returns_success(self, ctx: PhaseContext) -> None:
        phase = P6Phase(argv=["--clean"])
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, P6Output)
        assert result.data.mode == "clean"
        assert result.error is None
        assert result.duration_s > 0

    def test_execute_clean_with_stale_file(self, ctx: PhaseContext) -> None:
        lock_file = ctx.work_dir / "stale.lock"
        lock_file.write_text("lock")
        old_time = time.time() - 7200
        import os
        os.utime(lock_file, (old_time, old_time))

        phase = P6Phase(argv=["--clean"], stale_threshold_secs=3600)
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data.was_cleaned is True
        assert not lock_file.exists()


# ===================================================================
# execute end-to-end -- NO_CLEAN mode
# ===================================================================


class TestExecuteNoClean:
    """P6Phase.execute() end-to-end in no-clean mode."""

    def test_execute_no_clean_returns_success(self, ctx: PhaseContext) -> None:
        phase = P6Phase(argv=["--no-clean"])
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.mode == "no-clean"
        assert result.data.was_skipped is True
        assert result.error is None


# ===================================================================
# execute end-to-end -- CHECK mode
# ===================================================================


class TestExecuteCheck:
    """P6Phase.execute() end-to-end in check mode (captured exit)."""

    def test_execute_check_returns_success(self, ctx: PhaseContext) -> None:
        phase = P6Phase(argv=["--check"])
        result = phase.execute(ctx)

        # Check mode still succeeds because we capture the exit.
        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None


# ===================================================================
# execute with custom work_dirs
# ===================================================================


class TestExecuteCustomWorkDirs:
    """P6Phase.execute() with explicit work directories."""

    def test_custom_work_dirs_used(self, ctx: PhaseContext, tmp_path: Path) -> None:
        custom_dir = tmp_path / "custom_work"
        custom_dir.mkdir()

        phase = P6Phase(work_dirs=[custom_dir], argv=["--clean"])
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data.mode == "clean"
