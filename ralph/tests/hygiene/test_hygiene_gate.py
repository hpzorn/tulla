"""Tests for hygiene control flow gate."""

import io
from pathlib import Path
from unittest.mock import MagicMock

from ralph.hygiene.args import HygieneMode
from ralph.hygiene.gate import GateResult, hygiene_gate


class TestHygieneGateCleanMode:
    """Tests for the gate in CLEAN mode (default)."""

    def test_clean_mode_returns_gate_result(self, tmp_path: Path) -> None:
        result = hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=[],
        )
        assert isinstance(result, GateResult)
        assert result.config.mode == HygieneMode.CLEAN

    def test_clean_mode_returns_report(self, tmp_path: Path) -> None:
        result = hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=["--clean"],
        )
        assert result.report is not None
        assert result.report.mode_used == "clean"

    def test_clean_mode_passes_remaining_args(self, tmp_path: Path) -> None:
        result = hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=["--clean", "--idea", "42", "--verbose"],
        )
        assert result.remaining_args == ["--idea", "42", "--verbose"]

    def test_clean_mode_cleans_stale_lock_file(self, tmp_path: Path) -> None:
        import os
        import time

        lock_file = tmp_path / "stale.lock"
        lock_file.write_text("locked")
        # Set mtime to 2 hours ago to exceed the default 1-hour threshold.
        old_time = time.time() - 7200
        os.utime(lock_file, (old_time, old_time))

        result = hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=["--clean"],
        )
        assert result.report is not None
        assert result.report.cleaned_count >= 1
        assert not lock_file.exists()

    def test_clean_mode_no_stale_files(self, tmp_path: Path) -> None:
        result = hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=["--clean"],
        )
        assert result.report is not None
        assert result.report.is_clean


class TestHygieneGateNoCleanMode:
    """Tests for the gate in NO_CLEAN mode."""

    def test_no_clean_mode_skips_hygiene(self, tmp_path: Path) -> None:
        result = hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=["--no-clean"],
        )
        assert result.config.mode == HygieneMode.NO_CLEAN
        assert result.report is None

    def test_no_clean_mode_passes_remaining_args(self, tmp_path: Path) -> None:
        result = hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=["--no-clean", "--rounds", "5"],
        )
        assert result.remaining_args == ["--rounds", "5"]

    def test_no_clean_mode_does_not_remove_files(self, tmp_path: Path) -> None:
        import os
        import time

        lock_file = tmp_path / "stale.lock"
        lock_file.write_text("locked")
        old_time = time.time() - 7200
        os.utime(lock_file, (old_time, old_time))

        hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=["--no-clean"],
        )
        # File should still exist because hygiene was skipped.
        assert lock_file.exists()


class TestHygieneGateCheckMode:
    """Tests for the gate in CHECK mode (exits the process)."""

    def test_check_mode_calls_exit_func(self, tmp_path: Path) -> None:
        mock_exit = MagicMock()
        buf = io.StringIO()

        hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=["--check"],
            exit_func=mock_exit,
            output_stream=buf,
        )
        mock_exit.assert_called_once_with(0)

    def test_check_mode_exit_code_0_when_clean(self, tmp_path: Path) -> None:
        mock_exit = MagicMock()
        buf = io.StringIO()

        hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=["--check"],
            exit_func=mock_exit,
            output_stream=buf,
        )
        mock_exit.assert_called_once_with(0)
        assert "clean" in buf.getvalue().lower()

    def test_check_mode_exit_code_1_when_stale(self, tmp_path: Path) -> None:
        import os
        import time

        mock_exit = MagicMock()
        buf = io.StringIO()

        lock_file = tmp_path / "old.lock"
        lock_file.write_text("locked")
        old_time = time.time() - 7200
        os.utime(lock_file, (old_time, old_time))

        hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=["--check"],
            exit_func=mock_exit,
            output_stream=buf,
        )
        mock_exit.assert_called_once_with(1)

    def test_check_mode_does_not_remove_files(self, tmp_path: Path) -> None:
        import os
        import time

        mock_exit = MagicMock()
        buf = io.StringIO()

        lock_file = tmp_path / "stale.lock"
        lock_file.write_text("locked")
        old_time = time.time() - 7200
        os.utime(lock_file, (old_time, old_time))

        hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=["--check"],
            exit_func=mock_exit,
            output_stream=buf,
        )
        # Check mode should NOT remove files.
        assert lock_file.exists()

    def test_check_mode_passes_remaining_args_in_fallthrough(
        self, tmp_path: Path
    ) -> None:
        """When exit_func doesn't actually exit, remaining_args are available."""
        mock_exit = MagicMock()
        buf = io.StringIO()

        result = hygiene_gate(
            script_name="test-script",
            work_dirs=[tmp_path],
            argv=["--check", "--idea", "7"],
            exit_func=mock_exit,
            output_stream=buf,
        )
        assert result.remaining_args == ["--idea", "7"]


class TestHygieneGateMultipleDirectories:
    """Tests for the gate inspecting multiple work directories."""

    def test_inspects_all_directories(self, tmp_path: Path) -> None:
        import os
        import time

        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        lock_a = dir_a / "stale_a.lock"
        lock_b = dir_b / "stale_b.lock"
        lock_a.write_text("locked")
        lock_b.write_text("locked")
        old_time = time.time() - 7200
        os.utime(lock_a, (old_time, old_time))
        os.utime(lock_b, (old_time, old_time))

        result = hygiene_gate(
            script_name="test-script",
            work_dirs=[dir_a, dir_b],
            argv=["--clean"],
        )
        assert result.report is not None
        assert result.report.cleaned_count == 2
        assert not lock_a.exists()
        assert not lock_b.exists()


class TestGateResult:
    """Tests for the GateResult dataclass."""

    def test_frozen(self) -> None:
        from ralph.hygiene.args import HygieneConfig

        config = HygieneConfig(mode=HygieneMode.CLEAN, remaining_args=[])
        gate_result = GateResult(config=config, report=None)
        try:
            gate_result.config = config  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass

    def test_default_remaining_args(self) -> None:
        from ralph.hygiene.args import HygieneConfig

        config = HygieneConfig(mode=HygieneMode.CLEAN, remaining_args=[])
        gate_result = GateResult(config=config, report=None)
        assert gate_result.remaining_args == []
