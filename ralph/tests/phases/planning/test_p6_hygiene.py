"""Tests for the planning-ralph P6 hygiene phase integration.

Verifies that:
1. The P6 phase correctly wires the ralph.hygiene shared library.
2. All hygiene modes (clean, no-clean, check) work through the P6 entry point.
3. Trap handler is installed and cleanup callable is returned.
4. Pre-flight decision logging is invoked with correct metadata.
5. Remaining CLI args are correctly passed through.
6. Help display works via --help flag.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from ralph.phases.planning.p6 import (
    DEFAULT_WORK_DIRS,
    P6PhaseResult,
    SCRIPT_DESCRIPTION,
    SCRIPT_NAME,
    run_p6_phase,
)


class TestP6PhaseConstants:
    """Verify module-level constants are properly defined."""

    def test_script_name(self) -> None:
        assert SCRIPT_NAME == "planning-ralph"

    def test_script_description(self) -> None:
        assert "planning" in SCRIPT_DESCRIPTION.lower()

    def test_default_work_dirs(self) -> None:
        assert len(DEFAULT_WORK_DIRS) == 1
        assert DEFAULT_WORK_DIRS[0] == Path("./work")


class TestP6PhaseCleanMode:
    """Test P6 phase in --clean mode (default)."""

    def test_clean_mode_default(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=[],
            exit_func=lambda code: None,
        )
        assert isinstance(result, P6PhaseResult)
        assert result.gate_result.config.should_clean is True
        assert result.was_cleaned is True
        assert result.was_skipped is False
        assert result.remaining_args == []

    def test_clean_mode_explicit(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--clean"],
            exit_func=lambda code: None,
        )
        assert result.gate_result.config.should_clean is True
        assert result.decision.mode == "clean"
        assert result.decision.source == "explicit"

    def test_clean_mode_passes_remaining_args(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--clean", "--rounds", "3", "--idea", "42"],
            exit_func=lambda code: None,
        )
        assert result.remaining_args == ["--rounds", "3", "--idea", "42"]

    def test_clean_mode_with_stale_files(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "stale.lock"
        lock_file.write_text("locked")
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--clean"],
            stale_threshold_secs=0,
            exit_func=lambda code: None,
        )
        assert result.report is not None
        assert result.report.cleaned_count == 1
        assert not lock_file.exists()

    def test_clean_mode_report_summary(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=[],
            exit_func=lambda code: None,
        )
        summary = result.summary()
        assert "P6 phase complete" in summary
        assert "clean" in summary


class TestP6PhaseNoCleanMode:
    """Test P6 phase in --no-clean mode."""

    def test_no_clean_skips_hygiene(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "stale.lock"
        lock_file.write_text("locked")
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--no-clean"],
            stale_threshold_secs=0,
            exit_func=lambda code: None,
        )
        assert result.was_skipped is True
        assert result.was_cleaned is False
        assert result.report is None
        assert lock_file.exists()  # Not removed

    def test_no_clean_decision_logged(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--no-clean"],
            exit_func=lambda code: None,
        )
        assert result.decision.mode == "no-clean"
        assert result.decision.source == "explicit"
        assert result.decision.script_name == SCRIPT_NAME

    def test_no_clean_summary(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--no-clean"],
            exit_func=lambda code: None,
        )
        summary = result.summary()
        assert "skipped" in summary


class TestP6PhaseCheckMode:
    """Test P6 phase in --check mode."""

    def test_check_mode_exits(self, tmp_path: Path) -> None:
        exit_codes: list[int] = []
        buf = io.StringIO()
        run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--check"],
            exit_func=lambda code: exit_codes.append(code),
            output_stream=buf,
        )
        assert exit_codes == [0]

    def test_check_mode_reports_stale(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "stale.lock"
        lock_file.write_text("locked")
        exit_codes: list[int] = []
        buf = io.StringIO()
        run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--check"],
            stale_threshold_secs=0,
            exit_func=lambda code: exit_codes.append(code),
            output_stream=buf,
        )
        assert exit_codes == [1]
        assert lock_file.exists()  # Not removed in check mode
        output = buf.getvalue()
        assert "stale" in output.lower() or "issue" in output.lower()

    def test_check_mode_clean_workspace_output(self, tmp_path: Path) -> None:
        exit_codes: list[int] = []
        buf = io.StringIO()
        run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--check"],
            exit_func=lambda code: exit_codes.append(code),
            output_stream=buf,
        )
        assert exit_codes == [0]
        assert "clean" in buf.getvalue().lower()


class TestP6PhaseTrapHandler:
    """Test that the P6 phase installs a trap handler."""

    def test_cleanup_callable_returned(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--clean"],
            exit_func=lambda code: None,
        )
        assert callable(result.cleanup)
        # Calling cleanup should not raise.
        result.cleanup()

    def test_cleanup_idempotent(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--clean"],
            exit_func=lambda code: None,
        )
        # Multiple calls should be safe.
        result.cleanup()
        result.cleanup()


class TestP6PhaseDecisionLogging:
    """Test that the P6 phase logs pre-flight decisions correctly."""

    def test_decision_script_name(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--clean"],
            exit_func=lambda code: None,
        )
        assert result.decision.script_name == "planning-ralph"

    def test_decision_work_dirs(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--clean"],
            exit_func=lambda code: None,
        )
        assert str(tmp_path) in result.decision.work_dirs

    def test_decision_remaining_args(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--clean", "--idea", "7"],
            exit_func=lambda code: None,
        )
        assert result.decision.remaining_args == ["--idea", "7"]

    def test_decision_default_source(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=[],
            exit_func=lambda code: None,
        )
        assert result.decision.source == "default"

    def test_decision_serializable(self, tmp_path: Path) -> None:
        import json

        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--clean"],
            exit_func=lambda code: None,
        )
        # Should be serializable to JSON without error.
        json_str = result.decision.as_json()
        parsed = json.loads(json_str)
        assert parsed["script_name"] == "planning-ralph"


class TestP6PhaseHelpFlag:
    """Test that --help triggers help display."""

    def test_help_flag_exits(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        exit_codes: list[int] = []
        run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--help"],
            exit_func=lambda code: exit_codes.append(code),
        )
        assert exit_codes == [0]
        captured = capsys.readouterr()
        assert "planning-ralph" in captured.out
        assert "Hygiene Options:" in captured.out

    def test_h_flag_exits(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        exit_codes: list[int] = []
        run_p6_phase(
            work_dirs=[tmp_path],
            argv=["-h"],
            exit_func=lambda code: exit_codes.append(code),
        )
        assert exit_codes == [0]


class TestP6PhaseResult:
    """Test P6PhaseResult dataclass properties."""

    def test_result_properties_clean(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--clean"],
            exit_func=lambda code: None,
        )
        assert result.was_cleaned is True
        assert result.was_skipped is False
        assert result.report is not None

    def test_result_properties_no_clean(self, tmp_path: Path) -> None:
        result = run_p6_phase(
            work_dirs=[tmp_path],
            argv=["--no-clean"],
            exit_func=lambda code: None,
        )
        assert result.was_cleaned is False
        assert result.was_skipped is True
        assert result.report is None

    def test_multiple_work_dirs(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        result = run_p6_phase(
            work_dirs=[dir_a, dir_b],
            argv=["--clean"],
            exit_func=lambda code: None,
        )
        assert result.was_cleaned is True
