"""Tests for hygiene check mode function."""

import io
import os
import time
from pathlib import Path

import pytest

from tulla.hygiene.check import (
    check_mode_exit_code,
    run_check_mode,
    run_check_mode_cli,
)
from tulla.hygiene.preflight import HygieneReport, StaleFile


class TestRunCheckMode:
    """Tests for run_check_mode function."""

    def test_returns_check_mode_report(self, tmp_path: Path) -> None:
        report = run_check_mode([tmp_path])
        assert report.mode_used == "check"

    def test_clean_directory_has_no_stale_files(self, tmp_path: Path) -> None:
        report = run_check_mode([tmp_path])
        assert report.is_clean is True
        assert report.issues_found == 0

    def test_never_cleans_files(self, tmp_path: Path) -> None:
        # Create an old lock file that would be cleaned in clean mode.
        lock_file = tmp_path / "stale.lock"
        lock_file.write_text("lock")
        old_time = time.time() - 7200  # 2 hours old
        os.utime(lock_file, (old_time, old_time))

        report = run_check_mode([tmp_path], stale_threshold_secs=3600)
        assert report.cleaned_count == 0
        assert lock_file.exists(), "Check mode must not remove files"

    def test_detects_stale_lock_file(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "stale.lock"
        lock_file.write_text("lock")
        old_time = time.time() - 7200
        os.utime(lock_file, (old_time, old_time))

        report = run_check_mode([tmp_path], stale_threshold_secs=3600)
        assert report.issues_found == 1
        assert report.stale_files[0].category == "lock"

    def test_detects_stale_temp_file(self, tmp_path: Path) -> None:
        temp_file = tmp_path / "data.tmp"
        temp_file.write_text("temp data")
        old_time = time.time() - 7200
        os.utime(temp_file, (old_time, old_time))

        report = run_check_mode([tmp_path], stale_threshold_secs=3600)
        assert report.issues_found == 1
        assert report.stale_files[0].category == "temp"

    def test_detects_orphaned_pid_file(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "worker.pid"
        # Use a PID that is very unlikely to be running.
        pid_file.write_text("9999999")

        report = run_check_mode([tmp_path])
        assert report.issues_found == 1
        assert report.stale_files[0].category == "pid"

    def test_multiple_directories(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        lock_a = dir_a / "a.lock"
        lock_b = dir_b / "b.lock"
        lock_a.write_text("lock")
        lock_b.write_text("lock")
        old_time = time.time() - 7200
        os.utime(lock_a, (old_time, old_time))
        os.utime(lock_b, (old_time, old_time))

        report = run_check_mode([dir_a, dir_b], stale_threshold_secs=3600)
        assert report.issues_found == 2

    def test_nonexistent_directory_returns_clean(self) -> None:
        report = run_check_mode([Path("/nonexistent/path/xyz")])
        assert report.is_clean is True

    def test_custom_threshold(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "recent.lock"
        lock_file.write_text("lock")
        # File is 10 seconds old.
        old_time = time.time() - 10
        os.utime(lock_file, (old_time, old_time))

        # With a 5-second threshold, it should be stale.
        report = run_check_mode([tmp_path], stale_threshold_secs=5)
        assert report.issues_found == 1

        # With a 60-second threshold, it should not be stale.
        report = run_check_mode([tmp_path], stale_threshold_secs=60)
        assert report.issues_found == 0


class TestCheckModeExitCode:
    """Tests for check_mode_exit_code function."""

    def test_clean_report_returns_zero(self) -> None:
        report = HygieneReport(mode_used="check")
        assert check_mode_exit_code(report) == 0

    def test_dirty_report_returns_one(self) -> None:
        report = HygieneReport(
            stale_files=[
                StaleFile(
                    path=Path("/tmp/stale.lock"),
                    category="lock",
                    age_secs=7200.0,
                    reason="old lock",
                ),
            ],
            mode_used="check",
        )
        assert check_mode_exit_code(report) == 1


class TestRunCheckModeCli:
    """Tests for run_check_mode_cli function."""

    def test_clean_workspace_prints_clean_message(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        code = run_check_mode_cli([tmp_path], output_stream=buf)
        assert code == 0
        assert "clean" in buf.getvalue().lower()

    def test_dirty_workspace_prints_details(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "stale.lock"
        lock_file.write_text("lock")
        old_time = time.time() - 7200
        os.utime(lock_file, (old_time, old_time))

        buf = io.StringIO()
        code = run_check_mode_cli(
            [tmp_path], stale_threshold_secs=3600, output_stream=buf,
        )
        assert code == 1
        output = buf.getvalue()
        assert "stale.lock" in output
        assert "[lock]" in output

    def test_returns_exit_code_zero_for_nonexistent_dir(self) -> None:
        buf = io.StringIO()
        code = run_check_mode_cli([Path("/nonexistent")], output_stream=buf)
        assert code == 0

    def test_defaults_to_stdout(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        code = run_check_mode_cli([tmp_path])
        assert code == 0
        captured = capsys.readouterr()
        assert "clean" in captured.out.lower()

    def test_multiple_stale_files_all_listed(self, tmp_path: Path) -> None:
        old_time = time.time() - 7200
        for name in ["a.lock", "b.tmp", "c.temp"]:
            f = tmp_path / name
            f.write_text("data")
            os.utime(f, (old_time, old_time))

        buf = io.StringIO()
        code = run_check_mode_cli(
            [tmp_path], stale_threshold_secs=3600, output_stream=buf,
        )
        assert code == 1
        output = buf.getvalue()
        assert "a.lock" in output
        assert "b.tmp" in output
        assert "c.temp" in output
