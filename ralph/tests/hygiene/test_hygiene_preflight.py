"""Tests for pre-flight hygiene function."""

import os
import time
from pathlib import Path

import pytest

from tulla.hygiene.args import HygieneConfig, HygieneMode
from tulla.hygiene.preflight import (
    ALL_CLEANABLE_SUFFIXES,
    DEFAULT_STALE_THRESHOLD_SECS,
    LOCK_SUFFIXES,
    PID_SUFFIXES,
    TEMP_SUFFIXES,
    HygieneReport,
    StaleFile,
    inspect_directory,
    run_preflight_hygiene,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(mode: HygieneMode) -> HygieneConfig:
    return HygieneConfig(mode=mode, remaining_args=[])


def _touch(path: Path, age_secs: float = 0) -> Path:
    """Create a file and optionally backdate its mtime."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("test")
    if age_secs > 0:
        old_time = time.time() - age_secs
        os.utime(path, (old_time, old_time))
    return path


# ---------------------------------------------------------------------------
# StaleFile dataclass
# ---------------------------------------------------------------------------

class TestStaleFile:
    def test_creation(self, tmp_path: Path) -> None:
        sf = StaleFile(
            path=tmp_path / "a.lock",
            category="lock",
            age_secs=7200.0,
            reason="stale lock",
        )
        assert sf.path == tmp_path / "a.lock"
        assert sf.category == "lock"
        assert sf.age_secs == 7200.0
        assert sf.reason == "stale lock"

    def test_frozen(self, tmp_path: Path) -> None:
        sf = StaleFile(
            path=tmp_path / "a.lock",
            category="lock",
            age_secs=0,
            reason="test",
        )
        with pytest.raises(AttributeError):
            sf.category = "temp"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# HygieneReport dataclass
# ---------------------------------------------------------------------------

class TestHygieneReport:
    def test_empty_report_is_clean(self) -> None:
        report = HygieneReport()
        assert report.is_clean is True
        assert report.issues_found == 0
        assert report.cleaned_count == 0

    def test_report_with_stale_files(self, tmp_path: Path) -> None:
        sf = StaleFile(
            path=tmp_path / "x.tmp",
            category="temp",
            age_secs=5000,
            reason="old",
        )
        report = HygieneReport(stale_files=[sf])
        assert report.is_clean is False
        assert report.issues_found == 1

    def test_summary_clean(self) -> None:
        report = HygieneReport()
        assert "clean" in report.summary().lower()

    def test_summary_check_mode(self, tmp_path: Path) -> None:
        sf = StaleFile(
            path=tmp_path / "x.lock",
            category="lock",
            age_secs=5000,
            reason="old",
        )
        report = HygieneReport(stale_files=[sf], mode_used="check")
        summary = report.summary()
        assert "check" in summary.lower()
        assert "1" in summary

    def test_summary_cleaned(self, tmp_path: Path) -> None:
        sf = StaleFile(
            path=tmp_path / "x.tmp",
            category="temp",
            age_secs=5000,
            reason="old",
        )
        report = HygieneReport(
            stale_files=[sf],
            cleaned_files=[tmp_path / "x.tmp"],
            mode_used="clean",
        )
        summary = report.summary()
        assert "cleaned" in summary.lower()
        assert "1" in summary

    def test_summary_with_errors(self, tmp_path: Path) -> None:
        sf = StaleFile(
            path=tmp_path / "x.lock",
            category="lock",
            age_secs=5000,
            reason="old",
        )
        report = HygieneReport(
            stale_files=[sf],
            errors=[(tmp_path / "x.lock", "permission denied")],
            mode_used="clean",
        )
        assert "error" in report.summary().lower()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_lock_suffixes(self) -> None:
        assert ".lock" in LOCK_SUFFIXES
        assert ".lck" in LOCK_SUFFIXES

    def test_temp_suffixes(self) -> None:
        assert ".tmp" in TEMP_SUFFIXES
        assert ".temp" in TEMP_SUFFIXES
        assert ".partial" in TEMP_SUFFIXES

    def test_pid_suffixes(self) -> None:
        assert ".pid" in PID_SUFFIXES

    def test_all_cleanable_is_union(self) -> None:
        assert ALL_CLEANABLE_SUFFIXES == LOCK_SUFFIXES | TEMP_SUFFIXES | PID_SUFFIXES

    def test_default_threshold(self) -> None:
        assert DEFAULT_STALE_THRESHOLD_SECS == 3600


# ---------------------------------------------------------------------------
# inspect_directory
# ---------------------------------------------------------------------------

class TestInspectDirectory:
    def test_empty_directory(self, tmp_path: Path) -> None:
        assert inspect_directory(tmp_path) == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        assert inspect_directory(tmp_path / "nope") == []

    def test_ignores_non_cleanable_files(self, tmp_path: Path) -> None:
        _touch(tmp_path / "data.json", age_secs=9999)
        _touch(tmp_path / "script.py", age_secs=9999)
        assert inspect_directory(tmp_path) == []

    def test_finds_stale_lock_file(self, tmp_path: Path) -> None:
        _touch(tmp_path / "run.lock", age_secs=7200)
        result = inspect_directory(tmp_path, stale_threshold_secs=3600)
        assert len(result) == 1
        assert result[0].category == "lock"
        assert result[0].path == tmp_path / "run.lock"

    def test_skips_fresh_lock_file(self, tmp_path: Path) -> None:
        _touch(tmp_path / "run.lock", age_secs=60)
        result = inspect_directory(tmp_path, stale_threshold_secs=3600)
        assert len(result) == 0

    def test_finds_stale_temp_file(self, tmp_path: Path) -> None:
        _touch(tmp_path / "output.tmp", age_secs=7200)
        result = inspect_directory(tmp_path, stale_threshold_secs=3600)
        assert len(result) == 1
        assert result[0].category == "temp"

    def test_finds_stale_partial_file(self, tmp_path: Path) -> None:
        _touch(tmp_path / "download.partial", age_secs=7200)
        result = inspect_directory(tmp_path, stale_threshold_secs=3600)
        assert len(result) == 1
        assert result[0].category == "temp"

    def test_pid_file_dead_process(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "worker.pid"
        pid_file.write_text("999999999")  # almost certainly not running
        result = inspect_directory(tmp_path)
        assert len(result) == 1
        assert result[0].category == "pid"
        assert "999999999" in result[0].reason

    def test_pid_file_alive_process(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "self.pid"
        pid_file.write_text(str(os.getpid()))  # our own PID is alive
        result = inspect_directory(tmp_path)
        assert len(result) == 0

    def test_pid_file_invalid_content(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "bad.pid"
        pid_file.write_text("not-a-number")
        result = inspect_directory(tmp_path)
        assert len(result) == 1
        assert "unreadable" in result[0].reason.lower() or "invalid" in result[0].reason.lower()

    def test_recurses_subdirectories(self, tmp_path: Path) -> None:
        subdir = tmp_path / "sub" / "deep"
        _touch(subdir / "old.lock", age_secs=7200)
        result = inspect_directory(tmp_path, stale_threshold_secs=3600)
        assert len(result) == 1
        assert "sub" in str(result[0].path)

    def test_multiple_stale_files(self, tmp_path: Path) -> None:
        _touch(tmp_path / "a.lock", age_secs=7200)
        _touch(tmp_path / "b.tmp", age_secs=7200)
        _touch(tmp_path / "c.temp", age_secs=7200)
        result = inspect_directory(tmp_path, stale_threshold_secs=3600)
        assert len(result) == 3

    def test_custom_threshold(self, tmp_path: Path) -> None:
        _touch(tmp_path / "x.lock", age_secs=120)
        assert len(inspect_directory(tmp_path, stale_threshold_secs=60)) == 1
        assert len(inspect_directory(tmp_path, stale_threshold_secs=300)) == 0


# ---------------------------------------------------------------------------
# run_preflight_hygiene
# ---------------------------------------------------------------------------

class TestRunPreflightHygiene:
    def test_no_clean_mode_skips_everything(self, tmp_path: Path) -> None:
        _touch(tmp_path / "stale.lock", age_secs=9999)
        config = _make_config(HygieneMode.NO_CLEAN)
        report = run_preflight_hygiene(config, [tmp_path])
        assert report.mode_used == "no-clean"
        assert report.is_clean is True
        assert (tmp_path / "stale.lock").exists()

    def test_check_mode_reports_but_does_not_delete(self, tmp_path: Path) -> None:
        _touch(tmp_path / "stale.lock", age_secs=7200)
        config = _make_config(HygieneMode.CHECK)
        report = run_preflight_hygiene(
            config, [tmp_path], stale_threshold_secs=3600,
        )
        assert report.mode_used == "check"
        assert report.issues_found == 1
        assert report.cleaned_count == 0
        assert (tmp_path / "stale.lock").exists()

    def test_clean_mode_deletes_stale_files(self, tmp_path: Path) -> None:
        _touch(tmp_path / "stale.tmp", age_secs=7200)
        config = _make_config(HygieneMode.CLEAN)
        report = run_preflight_hygiene(
            config, [tmp_path], stale_threshold_secs=3600,
        )
        assert report.mode_used == "clean"
        assert report.issues_found == 1
        assert report.cleaned_count == 1
        assert not (tmp_path / "stale.tmp").exists()

    def test_clean_mode_preserves_fresh_files(self, tmp_path: Path) -> None:
        _touch(tmp_path / "fresh.lock", age_secs=10)
        config = _make_config(HygieneMode.CLEAN)
        report = run_preflight_hygiene(
            config, [tmp_path], stale_threshold_secs=3600,
        )
        assert report.is_clean is True
        assert (tmp_path / "fresh.lock").exists()

    def test_clean_multiple_directories(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        _touch(dir_a / "x.lock", age_secs=7200)
        _touch(dir_b / "y.tmp", age_secs=7200)
        config = _make_config(HygieneMode.CLEAN)
        report = run_preflight_hygiene(
            config, [dir_a, dir_b], stale_threshold_secs=3600,
        )
        assert report.cleaned_count == 2
        assert not (dir_a / "x.lock").exists()
        assert not (dir_b / "y.tmp").exists()

    def test_clean_with_no_stale_files(self, tmp_path: Path) -> None:
        config = _make_config(HygieneMode.CLEAN)
        report = run_preflight_hygiene(config, [tmp_path])
        assert report.is_clean is True
        assert report.cleaned_count == 0

    def test_clean_handles_deletion_error(self, tmp_path: Path) -> None:
        lock_file = _touch(tmp_path / "readonly.lock", age_secs=7200)
        # Make the parent directory read-only so unlink fails.
        tmp_path.chmod(0o555)
        try:
            config = _make_config(HygieneMode.CLEAN)
            report = run_preflight_hygiene(
                config, [tmp_path], stale_threshold_secs=3600,
            )
            assert report.issues_found == 1
            assert len(report.errors) == 1
            assert report.cleaned_count == 0
        finally:
            tmp_path.chmod(0o755)

    def test_empty_directories_list(self) -> None:
        config = _make_config(HygieneMode.CLEAN)
        report = run_preflight_hygiene(config, [])
        assert report.is_clean is True

    def test_clean_dead_pid_file(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "worker.pid"
        pid_file.write_text("999999999")
        config = _make_config(HygieneMode.CLEAN)
        report = run_preflight_hygiene(config, [tmp_path])
        assert report.cleaned_count == 1
        assert not pid_file.exists()

    def test_clean_preserves_alive_pid(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "self.pid"
        pid_file.write_text(str(os.getpid()))
        config = _make_config(HygieneMode.CLEAN)
        report = run_preflight_hygiene(config, [tmp_path])
        assert report.is_clean is True
        assert pid_file.exists()
