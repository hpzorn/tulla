"""Tests for ralph.core.checkpoint module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ralph.core.checkpoint import CheckpointStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> CheckpointStore:
    """CheckpointStore backed by a temporary directory."""
    return CheckpointStore(work_dir=tmp_path)


# ===================================================================
# save / load round-trip
# ===================================================================


class TestSaveLoadRoundTrip:
    """save() then load() must return identical data."""

    def test_simple_dict_round_trip(self, store: CheckpointStore) -> None:
        data = {"status": "SUCCESS", "data": [1, 2, 3], "extra": "info"}
        store.save("phase-1", data)
        loaded = store.load("phase-1")
        assert loaded == data

    def test_nested_dict_round_trip(self, store: CheckpointStore) -> None:
        data = {
            "status": "SUCCESS",
            "data": {"nested": {"deep": True}},
            "metadata": {"attempt": 1},
        }
        store.save("phase-2", data)
        loaded = store.load("phase-2")
        assert loaded == data

    def test_overwrite_preserves_latest(self, store: CheckpointStore) -> None:
        store.save("phase-1", {"version": 1})
        store.save("phase-1", {"version": 2})
        loaded = store.load("phase-1")
        assert loaded == {"version": 2}


# ===================================================================
# load returns None for missing checkpoints
# ===================================================================


class TestLoadMissing:
    """load() must return None when no checkpoint exists."""

    def test_missing_checkpoint_returns_none(
        self, store: CheckpointStore
    ) -> None:
        assert store.load("nonexistent") is None

    def test_missing_after_other_save(self, store: CheckpointStore) -> None:
        store.save("phase-a", {"ok": True})
        assert store.load("phase-b") is None


# ===================================================================
# exists() correctness
# ===================================================================


class TestExists:
    """exists() boolean check tests."""

    def test_exists_false_before_save(self, store: CheckpointStore) -> None:
        assert store.exists("phase-1") is False

    def test_exists_true_after_save(self, store: CheckpointStore) -> None:
        store.save("phase-1", {"data": 1})
        assert store.exists("phase-1") is True

    def test_exists_false_for_other_phase(
        self, store: CheckpointStore
    ) -> None:
        store.save("phase-1", {"data": 1})
        assert store.exists("phase-2") is False


# ===================================================================
# list_checkpoints() sorting
# ===================================================================


class TestListCheckpoints:
    """list_checkpoints() must return sorted phase ids."""

    def test_empty_directory(self, store: CheckpointStore) -> None:
        assert store.list_checkpoints() == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        store = CheckpointStore(work_dir=tmp_path / "does-not-exist")
        assert store.list_checkpoints() == []

    def test_returns_sorted_phase_ids(self, store: CheckpointStore) -> None:
        store.save("phase-c", {"c": 3})
        store.save("phase-a", {"a": 1})
        store.save("phase-b", {"b": 2})
        assert store.list_checkpoints() == ["phase-a", "phase-b", "phase-c"]

    def test_ignores_non_checkpoint_files(
        self, store: CheckpointStore, tmp_path: Path
    ) -> None:
        store.save("phase-1", {"ok": True})
        # Create a file that does NOT match the checkpoint pattern
        (tmp_path / "random.txt").write_text("noise")
        assert store.list_checkpoints() == ["phase-1"]


# ===================================================================
# Atomic write safety
# ===================================================================


class TestAtomicWriteSafety:
    """save() must not leave corrupt files if writing fails mid-stream."""

    def test_failed_write_does_not_create_checkpoint(
        self, store: CheckpointStore
    ) -> None:
        with patch("ralph.core.checkpoint.json.dump", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                store.save("phase-x", {"will": "fail"})

        # No checkpoint should exist after the failure
        assert store.exists("phase-x") is False
        assert store.load("phase-x") is None

    def test_failed_write_preserves_previous_checkpoint(
        self, store: CheckpointStore
    ) -> None:
        store.save("phase-x", {"version": 1})

        with patch("ralph.core.checkpoint.json.dump", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                store.save("phase-x", {"version": 2})

        # The original checkpoint must still be intact
        loaded = store.load("phase-x")
        assert loaded == {"version": 1}

    def test_no_temp_files_left_on_failure(
        self, store: CheckpointStore, tmp_path: Path
    ) -> None:
        with patch("ralph.core.checkpoint.json.dump", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                store.save("phase-y", {"data": "test"})

        # No .tmp files should remain
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []
