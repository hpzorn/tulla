"""Tests for _find_latest_work_dir in tulla.cli."""

from __future__ import annotations

from pathlib import Path

from tulla.cli import _find_latest_work_dir


class TestFindLatestWorkDir:
    """Tests for work-dir auto-detection when --from is used."""

    def test_returns_most_recent_with_checkpoints(self, tmp_path: Path) -> None:
        """Picks the newest directory that has checkpoint files."""
        old = tmp_path / "idea-42-research-20260101-100000"
        old.mkdir()
        (old / "r1-result.json").write_text("{}")

        new = tmp_path / "idea-42-research-20260201-100000"
        new.mkdir()
        (new / "r1-result.json").write_text("{}")
        (new / "r2-result.json").write_text("{}")

        result = _find_latest_work_dir(tmp_path, 42, "research")
        assert result == new

    def test_skips_dirs_without_checkpoints(self, tmp_path: Path) -> None:
        """Skips directories that have no *-result.json files."""
        empty = tmp_path / "idea-42-research-20260201-120000"
        empty.mkdir()

        with_ckpt = tmp_path / "idea-42-research-20260101-100000"
        with_ckpt.mkdir()
        (with_ckpt / "r1-result.json").write_text("{}")

        result = _find_latest_work_dir(tmp_path, 42, "research")
        assert result == with_ckpt

    def test_returns_none_when_no_dirs(self, tmp_path: Path) -> None:
        """Returns None when work_base has no matching directories."""
        result = _find_latest_work_dir(tmp_path, 42, "research")
        assert result is None

    def test_returns_none_when_no_checkpoints(self, tmp_path: Path) -> None:
        """Returns None when directories exist but none have checkpoints."""
        d = tmp_path / "idea-42-research-20260201-100000"
        d.mkdir()
        (d / "some-other-file.md").write_text("hello")

        result = _find_latest_work_dir(tmp_path, 42, "research")
        assert result is None

    def test_returns_none_when_work_base_missing(self, tmp_path: Path) -> None:
        """Returns None when work_base does not exist."""
        result = _find_latest_work_dir(tmp_path / "nonexistent", 42, "research")
        assert result is None

    def test_ignores_other_agents(self, tmp_path: Path) -> None:
        """Only matches the specified agent name."""
        disc = tmp_path / "idea-42-discovery-20260201-100000"
        disc.mkdir()
        (disc / "d1-result.json").write_text("{}")

        result = _find_latest_work_dir(tmp_path, 42, "research")
        assert result is None

    def test_ignores_other_ideas(self, tmp_path: Path) -> None:
        """Only matches the specified idea id."""
        other = tmp_path / "idea-99-research-20260201-100000"
        other.mkdir()
        (other / "r1-result.json").write_text("{}")

        result = _find_latest_work_dir(tmp_path, 42, "research")
        assert result is None
