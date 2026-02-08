"""Tests for IntakePhase — change classification and lightweight eligibility.

# @pattern:EventSourcing -- Tests verify that IntakePhase produces correct immutable facts from mocked git state
# @principle:FailSafeRouting -- Tests verify that uncertain/refactor cases always route to full pipeline

Verification criteria (prd:req-53-2-1):
- Each of the 6 change types is correctly classified via keyword matching.
- The composite heuristic boundary conditions (5-file and 3-file thresholds).
- Single-package vs cross-package scope detection.
- The refactor-always-ineligible rule.
- Mocked git subprocess for affected file extraction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock
import subprocess

import pytest

from tulla.core.phase import PhaseContext, PhaseStatus
from tulla.phases.lightweight.intake import (
    IntakePhase,
    _classify_change,
    _compute_scope,
    _get_affected_files,
    _is_lightweight_eligible,
)
from tulla.phases.lightweight.models import IntakeOutput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def phase() -> IntakePhase:
    return IntakePhase()


@pytest.fixture()
def base_ctx(tmp_path: Path) -> PhaseContext:
    """Minimal PhaseContext with a change_description."""
    return PhaseContext(
        idea_id="test-idea",
        work_dir=tmp_path,
        config={"change_description": "Fix a bug in the parser"},
    )


def _make_ctx(tmp_path: Path, description: str, **extra: Any) -> PhaseContext:
    """Helper to build a PhaseContext with a custom description."""
    config: dict[str, Any] = {"change_description": description, **extra}
    return PhaseContext(idea_id="test-idea", work_dir=tmp_path, config=config)


def _mock_git_diff(files: list[str]) -> list[MagicMock]:
    """Create mock subprocess.run results for git diff + rev-parse.

    Returns a list of two mocks suitable for ``side_effect``:
    the first for ``git diff --name-only HEAD``, the second for
    ``git rev-parse --show-toplevel`` (returns CWD so prefix is empty
    and paths pass through unchanged).
    """
    diff_result = MagicMock()
    diff_result.returncode = 0
    diff_result.stdout = "\n".join(files) + "\n" if files else ""

    toplevel_result = MagicMock()
    toplevel_result.returncode = 0
    toplevel_result.stdout = str(Path.cwd()) + "\n"

    return [diff_result, toplevel_result]


# ---------------------------------------------------------------------------
# Tests: _classify_change — 6 change types
# ---------------------------------------------------------------------------


class TestClassifyChange:
    """Verify keyword-based classification into the 6-category taxonomy."""

    def test_bugfix_keywords(self) -> None:
        assert _classify_change("Fix null pointer in parser") == "bugfix"
        assert _classify_change("Bug in serialization logic") == "bugfix"
        assert _classify_change("Hotfix for production crash") == "bugfix"
        assert _classify_change("Patch memory leak") == "bugfix"

    def test_feature_keywords(self) -> None:
        assert _classify_change("Add user authentication") == "feature"
        assert _classify_change("Implement dark mode") == "feature"
        assert _classify_change("Create new API endpoint") == "feature"
        assert _classify_change("Introduce rate limiting") == "feature"

    def test_enhancement_keywords(self) -> None:
        assert _classify_change("Enhance logging output") == "enhancement"
        assert _classify_change("Improve error messages") == "enhancement"
        assert _classify_change("Update the logging schema") == "enhancement"
        assert _classify_change("Optimize query performance") == "enhancement"

    def test_chore_keywords(self) -> None:
        assert _classify_change("Chore: update dependencies") == "chore"
        assert _classify_change("CI pipeline configuration") == "chore"
        assert _classify_change("Bump version to 2.0") == "chore"
        assert _classify_change("Update build scripts") == "chore"

    def test_test_keywords(self) -> None:
        assert _classify_change("Add test for parser module") == "test"
        assert _classify_change("Improve coverage for auth") == "test"
        assert _classify_change("Add integration spec") == "test"

    def test_refactor_keywords(self) -> None:
        assert _classify_change("Refactor database layer") == "refactor"
        assert _classify_change("Restructure module layout") == "refactor"
        assert _classify_change("Clean up unused imports") == "refactor"

    def test_default_to_feature(self) -> None:
        """Unrecognised descriptions default to 'feature'."""
        assert _classify_change("some random change with no keywords") == "feature"
        assert _classify_change("") == "feature"

    def test_priority_bugfix_over_feature(self) -> None:
        """'fix' matches bugfix before 'add' could match feature."""
        assert _classify_change("Fix and add new handler") == "bugfix"

    def test_priority_test_over_feature(self) -> None:
        """'test' matches test before 'add' could match feature."""
        assert _classify_change("Add test for new feature") == "test"


# ---------------------------------------------------------------------------
# Tests: _get_affected_files — mocked git subprocess
# ---------------------------------------------------------------------------


class TestGetAffectedFiles:
    """Verify git diff extraction with mocked subprocess."""

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_returns_files_from_git_diff(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = _mock_git_diff(
            ["src/parser.py", "tests/test_parser.py"]
        )
        result = _get_affected_files()
        assert result == ["src/parser.py", "tests/test_parser.py"]
        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_returns_empty_on_nonzero_exit(self, mock_run: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_run.return_value = mock_result
        assert _get_affected_files() == []

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_returns_empty_on_file_not_found(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError("git not found")
        assert _get_affected_files() == []

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_returns_empty_on_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)
        assert _get_affected_files() == []

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_returns_empty_on_os_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = OSError("permission denied")
        assert _get_affected_files() == []

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_strips_blank_lines(self, mock_run: MagicMock) -> None:
        diff_result = MagicMock()
        diff_result.returncode = 0
        diff_result.stdout = "a.py\n\n  \nb.py\n"
        toplevel_result = MagicMock()
        toplevel_result.returncode = 0
        toplevel_result.stdout = str(Path.cwd()) + "\n"
        mock_run.side_effect = [diff_result, toplevel_result]
        assert _get_affected_files() == ["a.py", "b.py"]


# ---------------------------------------------------------------------------
# Tests: _compute_scope
# ---------------------------------------------------------------------------


class TestComputeScope:
    """Verify single-package vs cross-package scope detection."""

    def test_empty_files_single_package(self) -> None:
        assert _compute_scope([]) == "single-package"

    def test_single_top_level_dir(self) -> None:
        files = ["src/parser.py", "src/lexer.py", "src/utils/helpers.py"]
        assert _compute_scope(files) == "single-package"

    def test_multiple_top_level_dirs(self) -> None:
        files = ["src/parser.py", "tests/test_parser.py"]
        assert _compute_scope(files) == "cross-package"

    def test_root_files_same_dir(self) -> None:
        """Files at the root level share the same 'top dir' (the filename)."""
        files = ["README.md"]
        assert _compute_scope(files) == "single-package"

    def test_root_files_different_names(self) -> None:
        """Two root-level files have different top-level parts."""
        files = ["README.md", "setup.py"]
        assert _compute_scope(files) == "cross-package"

    def test_forward_slash_paths(self) -> None:
        """Git output typically uses forward slashes."""
        files = ["pkg/module/a.py", "pkg/module/b.py"]
        assert _compute_scope(files) == "single-package"

    def test_three_top_level_dirs(self) -> None:
        files = ["src/a.py", "tests/b.py", "docs/c.md"]
        assert _compute_scope(files) == "cross-package"


# ---------------------------------------------------------------------------
# Tests: _is_lightweight_eligible — composite routing heuristic
# ---------------------------------------------------------------------------


class TestIsLightweightEligible:
    """Verify the composite routing heuristic and boundary conditions."""

    # -- refactor: always ineligible --

    def test_refactor_always_ineligible_zero_files(self) -> None:
        assert _is_lightweight_eligible("refactor", [], "single-package", "") is False

    def test_refactor_always_ineligible_few_files(self) -> None:
        files = ["src/a.py", "src/b.py"]
        assert _is_lightweight_eligible("refactor", files, "single-package", "") is False

    def test_refactor_always_ineligible_many_files(self) -> None:
        files = [f"src/{i}.py" for i in range(10)]
        assert _is_lightweight_eligible("refactor", files, "single-package", "") is False

    # -- bugfix / chore / test: eligible if files <= 5 --

    @pytest.mark.parametrize("change_type", ["bugfix", "chore", "test"])
    def test_eligible_at_5_files(self, change_type: str) -> None:
        files = [f"src/{i}.py" for i in range(5)]
        assert _is_lightweight_eligible(change_type, files, "single-package", "") is True

    @pytest.mark.parametrize("change_type", ["bugfix", "chore", "test"])
    def test_ineligible_at_6_files(self, change_type: str) -> None:
        files = [f"src/{i}.py" for i in range(6)]
        assert _is_lightweight_eligible(change_type, files, "single-package", "") is False

    @pytest.mark.parametrize("change_type", ["bugfix", "chore", "test"])
    def test_eligible_at_zero_files(self, change_type: str) -> None:
        assert _is_lightweight_eligible(change_type, [], "single-package", "") is True

    @pytest.mark.parametrize("change_type", ["bugfix", "chore", "test"])
    def test_eligible_cross_package_5_files(self, change_type: str) -> None:
        """bugfix/chore/test only check file count, not scope."""
        files = [f"src/{i}.py" for i in range(5)]
        assert _is_lightweight_eligible(change_type, files, "cross-package", "") is True

    # -- enhancement: eligible if files <= 3 AND single-package --

    def test_enhancement_eligible_3_files_single_package(self) -> None:
        files = ["src/a.py", "src/b.py", "src/c.py"]
        assert _is_lightweight_eligible("enhancement", files, "single-package", "") is True

    def test_enhancement_ineligible_4_files(self) -> None:
        files = [f"src/{i}.py" for i in range(4)]
        assert _is_lightweight_eligible("enhancement", files, "single-package", "") is False

    def test_enhancement_ineligible_cross_package(self) -> None:
        files = ["src/a.py", "tests/b.py"]
        assert _is_lightweight_eligible("enhancement", files, "cross-package", "") is False

    def test_enhancement_eligible_zero_files_single_package(self) -> None:
        assert _is_lightweight_eligible("enhancement", [], "single-package", "") is True

    def test_enhancement_ineligible_3_files_cross_package(self) -> None:
        """Even at 3 files, cross-package makes enhancement ineligible."""
        files = ["src/a.py", "src/b.py", "src/c.py"]
        assert _is_lightweight_eligible("enhancement", files, "cross-package", "") is False

    # -- feature: eligible if files <= 3, no new public interfaces, single-package --

    def test_feature_eligible_3_files_single_package(self) -> None:
        files = ["src/a.py", "src/b.py", "src/c.py"]
        assert _is_lightweight_eligible("feature", files, "single-package", "add button") is True

    def test_feature_ineligible_4_files(self) -> None:
        files = [f"src/{i}.py" for i in range(4)]
        assert _is_lightweight_eligible("feature", files, "single-package", "add button") is False

    def test_feature_ineligible_cross_package(self) -> None:
        files = ["src/a.py"]
        assert _is_lightweight_eligible("feature", files, "cross-package", "add button") is False

    def test_feature_ineligible_new_public_api(self) -> None:
        files = ["src/a.py"]
        assert _is_lightweight_eligible(
            "feature", files, "single-package", "Add new public API endpoint"
        ) is False

    def test_feature_ineligible_expose(self) -> None:
        files = ["src/a.py"]
        assert _is_lightweight_eligible(
            "feature", files, "single-package", "Expose internal service"
        ) is False

    def test_feature_eligible_zero_files(self) -> None:
        assert _is_lightweight_eligible("feature", [], "single-package", "add thing") is True

    # -- unknown type: defaults to ineligible (fail-safe) --

    def test_unknown_type_ineligible(self) -> None:
        assert _is_lightweight_eligible("unknown", [], "single-package", "") is False

    def test_empty_type_ineligible(self) -> None:
        assert _is_lightweight_eligible("", [], "single-package", "") is False


# ---------------------------------------------------------------------------
# Tests: IntakePhase.execute() — end-to-end with mocked git
# ---------------------------------------------------------------------------


class TestIntakePhaseExecute:
    """End-to-end tests for IntakePhase.execute() with mocked subprocess."""

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_bugfix_eligible(
        self, mock_run: MagicMock, phase: IntakePhase, tmp_path: Path
    ) -> None:
        mock_run.side_effect = _mock_git_diff(["src/parser.py", "src/lexer.py"])
        ctx = _make_ctx(tmp_path, "Fix null pointer bug")

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, IntakeOutput)
        assert result.data.change_type == "bugfix"
        assert result.data.affected_files == ["src/parser.py", "src/lexer.py"]
        assert result.data.scope == "single-package"
        assert result.data.lightweight_eligible is True

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_refactor_always_ineligible_e2e(
        self, mock_run: MagicMock, phase: IntakePhase, tmp_path: Path
    ) -> None:
        mock_run.side_effect = _mock_git_diff(["src/a.py"])
        ctx = _make_ctx(tmp_path, "Refactor module structure")

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.change_type == "refactor"
        assert result.data.lightweight_eligible is False

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_feature_cross_package_ineligible(
        self, mock_run: MagicMock, phase: IntakePhase, tmp_path: Path
    ) -> None:
        mock_run.side_effect = _mock_git_diff(["src/a.py", "tests/b.py"])
        ctx = _make_ctx(tmp_path, "Add new feature")

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.change_type == "feature"
        assert result.data.scope == "cross-package"
        assert result.data.lightweight_eligible is False

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_git_unavailable_empty_files(
        self, mock_run: MagicMock, phase: IntakePhase, tmp_path: Path
    ) -> None:
        mock_run.side_effect = FileNotFoundError("git not found")
        ctx = _make_ctx(tmp_path, "Fix a bug")

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.affected_files == []
        assert result.data.lightweight_eligible is True  # bugfix, 0 files <= 5

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_chore_at_boundary(
        self, mock_run: MagicMock, phase: IntakePhase, tmp_path: Path
    ) -> None:
        """Chore with exactly 5 files is eligible; 6 files is not."""
        files_5 = [f"src/{i}.py" for i in range(5)]
        mock_run.side_effect = _mock_git_diff(files_5)
        ctx = _make_ctx(tmp_path, "Chore: update deps")

        result = phase.execute(ctx)
        assert result.data is not None
        assert result.data.lightweight_eligible is True

        files_6 = [f"src/{i}.py" for i in range(6)]
        mock_run.side_effect = _mock_git_diff(files_6)

        result = phase.execute(ctx)
        assert result.data is not None
        assert result.data.lightweight_eligible is False

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_empty_description_defaults_to_feature(
        self, mock_run: MagicMock, phase: IntakePhase, tmp_path: Path
    ) -> None:
        mock_run.side_effect = _mock_git_diff([])
        ctx = _make_ctx(tmp_path, "")

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.change_type == "feature"

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_build_prompt_returns_empty(
        self, mock_run: MagicMock, phase: IntakePhase, tmp_path: Path
    ) -> None:
        ctx = _make_ctx(tmp_path, "Fix bug")
        assert phase.build_prompt(ctx) == ""

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_get_tools_returns_empty(
        self, mock_run: MagicMock, phase: IntakePhase, tmp_path: Path
    ) -> None:
        ctx = _make_ctx(tmp_path, "Fix bug")
        assert phase.get_tools(ctx) == []

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_phase_id(self, mock_run: MagicMock, phase: IntakePhase) -> None:
        assert phase.phase_id == "intake"

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_enhancement_at_boundary_3_files(
        self, mock_run: MagicMock, phase: IntakePhase, tmp_path: Path
    ) -> None:
        mock_run.side_effect = _mock_git_diff(
            ["src/a.py", "src/b.py", "src/c.py"]
        )
        ctx = _make_ctx(tmp_path, "Improve error handling")

        result = phase.execute(ctx)
        assert result.data is not None
        assert result.data.change_type == "enhancement"
        assert result.data.lightweight_eligible is True

    @patch("tulla.phases.lightweight.intake.subprocess.run")
    def test_test_type_eligible(
        self, mock_run: MagicMock, phase: IntakePhase, tmp_path: Path
    ) -> None:
        mock_run.side_effect = _mock_git_diff(
            ["tests/test_a.py", "tests/test_b.py"]
        )
        ctx = _make_ctx(tmp_path, "Add test for auth module")

        result = phase.execute(ctx)
        assert result.data is not None
        assert result.data.change_type == "test"
        assert result.data.scope == "single-package"
        assert result.data.lightweight_eligible is True
