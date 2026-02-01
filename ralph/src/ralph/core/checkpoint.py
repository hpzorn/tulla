"""CheckpointStore for persisting phase results with atomic writes."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


class CheckpointStore:
    """Persist and retrieve phase results as JSON files.

    Each checkpoint is stored as ``{work_dir}/{phase_id}-result.json``.
    Writes are atomic (write to a temporary file then rename) so that a
    crash mid-write never leaves a corrupt checkpoint on disk.
    """

    def __init__(self, work_dir: Path) -> None:
        self._work_dir = work_dir

    def save(self, phase_id: str, result_dict: dict[str, Any]) -> None:
        """Atomically write *result_dict* as the checkpoint for *phase_id*."""
        target = self._path_for(phase_id)
        target.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: create temp file in the same directory, write, then
        # rename.  os.rename is atomic on POSIX when src and dst are on the
        # same filesystem.
        fd, tmp_path_str = tempfile.mkstemp(
            dir=target.parent, suffix=".tmp"
        )
        tmp_path = Path(tmp_path_str)
        try:
            with open(fd, "w", encoding="utf-8") as fh:
                json.dump(result_dict, fh, indent=2)
            tmp_path.replace(target)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

    def load(self, phase_id: str) -> dict[str, Any] | None:
        """Return the stored dict for *phase_id*, or ``None`` if absent."""
        target = self._path_for(phase_id)
        if not target.exists():
            return None
        return json.loads(target.read_text(encoding="utf-8"))

    def exists(self, phase_id: str) -> bool:
        """Return whether a checkpoint exists for *phase_id*."""
        return self._path_for(phase_id).exists()

    def list_checkpoints(self) -> list[str]:
        """Return sorted phase_ids that have stored checkpoints."""
        if not self._work_dir.exists():
            return []
        return sorted(
            p.name.removesuffix("-result.json")
            for p in self._work_dir.glob("*-result.json")
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _path_for(self, phase_id: str) -> Path:
        """Return the checkpoint file path for *phase_id*."""
        return self._work_dir / f"{phase_id}-result.json"
