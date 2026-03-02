"""Tests for CommitPhase — especially the doubled-path fix."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tulla.phases.implementation.commit import CommitPhase
from tulla.phases.implementation.models import FindOutput


def _init_git(root: Path) -> None:
    """Initialise a throwaway git repo with one seed commit."""
    subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    (root / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "."], cwd=root, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "seed"],
        cwd=root,
        capture_output=True,
        check=True,
    )


class TestCommitDoubledPath:
    """Regression: LLM returns paths prefixed with project dir name."""

    def test_doubled_prefix_is_stripped(self, tmp_path: Path) -> None:
        """When file_path='ralph/src/foo.py' and project_root ends in
        'ralph/', CommitPhase should strip the leading 'ralph/' and
        still stage + commit the file."""
        project = tmp_path / "ralph"
        project.mkdir()
        _init_git(project)

        # Create a file at ralph/src/foo.py
        (project / "src").mkdir()
        (project / "src" / "foo.py").write_text("x = 1\n")

        req = FindOutput(
            requirement_id="req-1",
            title="test",
            # Path with doubled prefix — "ralph/src/foo.py"
            files=["ralph/src/foo.py"],
        )

        result = CommitPhase().execute(req, project_root=project)

        assert result.committed is True
        assert result.commit_hash  # non-empty

    def test_normal_path_still_works(self, tmp_path: Path) -> None:
        """A correct relative path (no doubled prefix) still commits."""
        project = tmp_path / "ralph"
        project.mkdir()
        _init_git(project)

        (project / "src").mkdir()
        (project / "src" / "bar.py").write_text("y = 2\n")

        req = FindOutput(
            requirement_id="req-2",
            title="test",
            files=["src/bar.py"],
        )

        result = CommitPhase().execute(req, project_root=project)

        assert result.committed is True

    def test_missing_file_skips_commit(self, tmp_path: Path) -> None:
        """A truly missing file results in no commit."""
        project = tmp_path / "ralph"
        project.mkdir()
        _init_git(project)

        req = FindOutput(
            requirement_id="req-3",
            title="test",
            files=["nonexistent/file.py"],
        )

        result = CommitPhase().execute(req, project_root=project)

        assert result.committed is False
