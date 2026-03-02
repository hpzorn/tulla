"""Tests for the tulla.hygiene shared library package.

Verifies that:
1. All public symbols are importable from the top-level package.
2. Internal module imports resolve correctly (no src. references).
3. Core functionality works via the shared library API.
4. The library can be used as a drop-in replacement for the old src.* modules.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest


class TestPackageImports:
    """Verify all public symbols are accessible from tulla.hygiene."""

    def test_import_top_level(self) -> None:
        import tulla.hygiene

        assert hasattr(tulla.hygiene, "__all__")

    def test_import_args_types(self) -> None:
        from tulla.hygiene import HygieneMode

        assert HygieneMode.CLEAN.value == "clean"
        assert HygieneMode.NO_CLEAN.value == "no-clean"
        assert HygieneMode.CHECK.value == "check"

    def test_import_preflight_types(self) -> None:
        from tulla.hygiene import (
            DEFAULT_STALE_THRESHOLD_SECS,
        )

        assert DEFAULT_STALE_THRESHOLD_SECS == 3600

    def test_import_check_functions(self) -> None:
        from tulla.hygiene import check_mode_exit_code, run_check_mode, run_check_mode_cli

        assert callable(run_check_mode)
        assert callable(run_check_mode_cli)
        assert callable(check_mode_exit_code)

    def test_import_gate(self) -> None:
        from tulla.hygiene import hygiene_gate

        assert callable(hygiene_gate)

    def test_import_help(self) -> None:
        from tulla.hygiene import (
            HYGIENE_HELP_HEADER,
        )

        assert "Hygiene Options:" in HYGIENE_HELP_HEADER

    def test_import_trap(self) -> None:
        from tulla.hygiene import TRAPPED_SIGNALS, install_trap_handler

        assert callable(install_trap_handler)
        assert len(TRAPPED_SIGNALS) == 2

    def test_import_startup_log(self) -> None:
        from tulla.hygiene import (
            log_preflight_decision,
        )

        assert callable(log_preflight_decision)

    def test_import_fact_update(self) -> None:
        from tulla.hygiene import (
            apply_fact_update,
        )

        assert callable(apply_fact_update)

    def test_all_exports_count(self) -> None:
        import tulla.hygiene

        # Verify we have a substantial public API
        assert len(tulla.hygiene.__all__) >= 25


class TestArgsViaLibrary:
    """Test argument parsing through the shared library."""

    def test_parse_clean(self) -> None:
        from tulla.hygiene import HygieneMode, parse_hygiene_args

        config = parse_hygiene_args(["--clean", "--idea", "42"])
        assert config.mode == HygieneMode.CLEAN
        assert config.remaining_args == ["--idea", "42"]

    def test_parse_no_clean(self) -> None:
        from tulla.hygiene import HygieneMode, parse_hygiene_args

        config = parse_hygiene_args(["--no-clean"])
        assert config.mode == HygieneMode.NO_CLEAN
        assert config.is_disabled is True

    def test_parse_check(self) -> None:
        from tulla.hygiene import HygieneMode, parse_hygiene_args

        config = parse_hygiene_args(["--check"])
        assert config.mode == HygieneMode.CHECK
        assert config.is_check_only is True

    def test_default_is_clean(self) -> None:
        from tulla.hygiene import parse_hygiene_args

        config = parse_hygiene_args([])
        assert config.should_clean is True


class TestPreflightViaLibrary:
    """Test pre-flight hygiene through the shared library."""

    def test_inspect_empty_directory(self, tmp_path: Path) -> None:
        from tulla.hygiene import inspect_directory

        result = inspect_directory(tmp_path)
        assert result == []

    def test_inspect_nonexistent_directory(self) -> None:
        from tulla.hygiene import inspect_directory

        result = inspect_directory(Path("/nonexistent/dir"))
        assert result == []

    def test_inspect_finds_stale_lock(self, tmp_path: Path) -> None:
        from tulla.hygiene import inspect_directory

        lock_file = tmp_path / "test.lock"
        lock_file.write_text("locked")
        # Use threshold of 0 so any file is "stale"
        result = inspect_directory(tmp_path, stale_threshold_secs=0)
        assert len(result) == 1
        assert result[0].category == "lock"

    def test_run_preflight_noclean_mode(self, tmp_path: Path) -> None:
        from tulla.hygiene import HygieneConfig, HygieneMode, run_preflight_hygiene

        config = HygieneConfig(mode=HygieneMode.NO_CLEAN, remaining_args=[])
        report = run_preflight_hygiene(config, [tmp_path])
        assert report.mode_used == "no-clean"
        assert report.is_clean is True

    def test_run_preflight_check_mode(self, tmp_path: Path) -> None:
        from tulla.hygiene import HygieneConfig, HygieneMode, run_preflight_hygiene

        lock_file = tmp_path / "stale.lock"
        lock_file.write_text("old")
        config = HygieneConfig(mode=HygieneMode.CHECK, remaining_args=[])
        report = run_preflight_hygiene(config, [tmp_path], stale_threshold_secs=0)
        assert report.mode_used == "check"
        assert report.issues_found == 1
        assert report.cleaned_count == 0
        assert lock_file.exists()  # Not removed in check mode

    def test_run_preflight_clean_mode(self, tmp_path: Path) -> None:
        from tulla.hygiene import HygieneConfig, HygieneMode, run_preflight_hygiene

        lock_file = tmp_path / "stale.lock"
        lock_file.write_text("old")
        config = HygieneConfig(mode=HygieneMode.CLEAN, remaining_args=[])
        report = run_preflight_hygiene(config, [tmp_path], stale_threshold_secs=0)
        assert report.mode_used == "clean"
        assert report.cleaned_count == 1
        assert not lock_file.exists()  # Actually removed


class TestCheckModeViaLibrary:
    """Test check mode through the shared library."""

    def test_check_mode_clean_workspace(self, tmp_path: Path) -> None:
        from tulla.hygiene import run_check_mode

        report = run_check_mode([tmp_path])
        assert report.is_clean is True
        assert report.mode_used == "check"

    def test_check_exit_code_clean(self) -> None:
        from tulla.hygiene import HygieneReport, check_mode_exit_code

        report = HygieneReport(mode_used="check")
        assert check_mode_exit_code(report) == 0

    def test_check_exit_code_issues(self) -> None:
        from tulla.hygiene import HygieneReport, StaleFile, check_mode_exit_code

        report = HygieneReport(
            stale_files=[StaleFile(Path("/x.lock"), "lock", 9999, "old")],
            mode_used="check",
        )
        assert check_mode_exit_code(report) == 1

    def test_check_mode_cli_output(self, tmp_path: Path) -> None:
        from tulla.hygiene import run_check_mode_cli

        buf = io.StringIO()
        code = run_check_mode_cli([tmp_path], output_stream=buf)
        assert code == 0
        assert "clean" in buf.getvalue()


class TestGateViaLibrary:
    """Test the hygiene gate through the shared library."""

    def test_gate_clean_mode(self, tmp_path: Path) -> None:
        from tulla.hygiene import hygiene_gate

        result = hygiene_gate(
            script_name="test",
            work_dirs=[tmp_path],
            argv=["--clean", "--idea", "42"],
        )
        assert result.config.should_clean is True
        assert result.remaining_args == ["--idea", "42"]
        assert result.report is not None

    def test_gate_noclean_mode(self, tmp_path: Path) -> None:
        from tulla.hygiene import hygiene_gate

        result = hygiene_gate(
            script_name="test",
            work_dirs=[tmp_path],
            argv=["--no-clean"],
        )
        assert result.config.is_disabled is True
        assert result.report is None

    def test_gate_check_mode_exits(self, tmp_path: Path) -> None:
        from tulla.hygiene import hygiene_gate

        exit_codes: list[int] = []
        buf = io.StringIO()
        hygiene_gate(
            script_name="test",
            work_dirs=[tmp_path],
            argv=["--check"],
            exit_func=lambda code: exit_codes.append(code),
            output_stream=buf,
        )
        assert exit_codes == [0]


class TestHelpViaLibrary:
    """Test help text through the shared library."""

    def test_help_text_contains_flags(self) -> None:
        from tulla.hygiene import get_hygiene_help_text

        text = get_hygiene_help_text()
        assert "--clean" in text
        assert "--no-clean" in text
        assert "--check" in text

    def test_inject_help(self) -> None:
        from tulla.hygiene import inject_hygiene_help

        text = inject_hygiene_help("test-tulla.sh", "Run tests.")
        assert "test-tulla.sh" in text
        assert "Hygiene Options:" in text


class TestTrapViaLibrary:
    """Test trap handler through the shared library."""

    def test_install_returns_cleanup(self) -> None:
        from tulla.hygiene import install_trap_handler

        cleanup = install_trap_handler(
            "test-script",
            exit_func=lambda code: None,
        )
        assert callable(cleanup)
        cleanup()  # Should not raise

    def test_trap_context(self) -> None:
        from tulla.hygiene import TrapContext

        ctx = TrapContext(script_name="test")
        assert ctx.script_name == "test"
        assert ctx.exit_logged is False
        assert ctx.elapsed_secs >= 0


class TestStartupLogViaLibrary:
    """Test startup logging through the shared library."""

    def test_build_decision_explicit(self) -> None:
        from tulla.hygiene import (
            HygieneConfig,
            HygieneMode,
            build_preflight_decision,
        )

        config = HygieneConfig(mode=HygieneMode.CHECK, remaining_args=[])
        decision = build_preflight_decision(
            "test-tulla",
            config,
            [Path("./work")],
            argv=["--check"],
        )
        assert decision.mode == "check"
        assert decision.source == "explicit"

    def test_build_decision_default(self) -> None:
        from tulla.hygiene import (
            HygieneConfig,
            HygieneMode,
            build_preflight_decision,
        )

        config = HygieneConfig(mode=HygieneMode.CLEAN, remaining_args=[])
        decision = build_preflight_decision(
            "test-tulla",
            config,
            [Path("./work")],
            argv=[],
        )
        assert decision.mode == "clean"
        assert decision.source == "default"

    def test_decision_json(self) -> None:
        import json

        from tulla.hygiene import PreflightDecision

        decision = PreflightDecision(
            script_name="test",
            mode="clean",
            source="default",
            work_dirs=["./work"],
            remaining_args=[],
        )
        parsed = json.loads(decision.as_json())
        assert parsed["script_name"] == "test"


class TestFactUpdateViaLibrary:
    """Test fact update through the shared library."""

    def test_validate_valid_update(self) -> None:
        from tulla.hygiene import FactUpdate, validate_fact_update

        update = FactUpdate("old1", "s", "p", "new_val")
        assert validate_fact_update(update) == []

    def test_validate_empty_fields(self) -> None:
        from tulla.hygiene import FactUpdate, validate_fact_update

        update = FactUpdate("", "", "", "")
        errors = validate_fact_update(update)
        assert len(errors) == 4

    def test_apply_forget_before_store(self) -> None:
        from tulla.hygiene import FactUpdate, apply_fact_update

        ops: list[tuple[str, Any]] = []

        def mock_store(**kw: Any) -> dict[str, Any]:
            ops.append(("store", kw))
            return {"fact_id": "new123"}

        def mock_forget(fid: str) -> dict[str, Any]:
            ops.append(("forget", fid))
            return {"status": "ok"}

        update = FactUpdate("old1", "subj", "pred", "new_val", context="ctx")
        result = apply_fact_update(update, store_fn=mock_store, forget_fn=mock_forget)

        assert result == {"fact_id": "new123"}
        assert ops[0][0] == "forget"  # Forget happens FIRST
        assert ops[1][0] == "store"  # Store happens SECOND
        assert ops[0][1] == "old1"

    def test_apply_batch_updates(self) -> None:
        from tulla.hygiene import FactUpdate, apply_fact_updates

        def mock_store(**kw: Any) -> dict[str, Any]:
            return {"fact_id": "new"}

        def mock_forget(fid: str) -> dict[str, Any]:
            return {"status": "ok"}

        updates = [
            FactUpdate("old1", "s1", "p1", "v1"),
            FactUpdate("old2", "s2", "p2", "v2"),
        ]
        results = apply_fact_updates(updates, store_fn=mock_store, forget_fn=mock_forget)
        assert len(results) == 2

    def test_apply_invalid_raises(self) -> None:
        from tulla.hygiene import FactUpdate, FactUpdateError, apply_fact_update

        update = FactUpdate("", "s", "p", "v")
        with pytest.raises(FactUpdateError) as exc_info:
            apply_fact_update(
                update,
                store_fn=lambda **kw: {},
                forget_fn=lambda fid: {},
            )
        assert exc_info.value.phase == "validation"
