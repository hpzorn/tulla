"""Tests for TullaConfig."""

from tulla.config import TullaConfig


def test_project_id_default():
    """project_id defaults to 'ralph'."""
    cfg = TullaConfig()
    assert cfg.project_id == "ralph"


def test_project_id_from_env(monkeypatch):
    """TULLA_PROJECT_ID environment variable overrides the default."""
    monkeypatch.setenv("TULLA_PROJECT_ID", "acme")
    cfg = TullaConfig()
    assert cfg.project_id == "acme"


def test_project_id_is_string():
    """project_id field is typed as str."""
    cfg = TullaConfig()
    assert isinstance(cfg.project_id, str)
