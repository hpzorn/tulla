"""Tests for tulla.hygiene.startup_log — pre-flight decision logging."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from tulla.hygiene.args import HygieneConfig, HygieneMode
from tulla.hygiene.startup_log import (
    PreflightDecision,
    _detect_source,
    build_preflight_decision,
    log_preflight_decision,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def clean_config() -> HygieneConfig:
    """HygieneConfig in CLEAN mode with no remaining args."""
    return HygieneConfig(mode=HygieneMode.CLEAN, remaining_args=[])


@pytest.fixture()
def check_config() -> HygieneConfig:
    """HygieneConfig in CHECK mode."""
    return HygieneConfig(mode=HygieneMode.CHECK, remaining_args=[])


@pytest.fixture()
def no_clean_config() -> HygieneConfig:
    """HygieneConfig in NO_CLEAN mode."""
    return HygieneConfig(mode=HygieneMode.NO_CLEAN, remaining_args=[])


@pytest.fixture()
def config_with_remaining() -> HygieneConfig:
    """HygieneConfig with remaining args passed through."""
    return HygieneConfig(mode=HygieneMode.CLEAN, remaining_args=["--idea", "42"])


@pytest.fixture()
def work_dirs() -> list[Path]:
    """Sample work directories."""
    return [Path("./work"), Path("/tmp/tulla-work")]


# ---------------------------------------------------------------------------
# PreflightDecision dataclass
# ---------------------------------------------------------------------------


class TestPreflightDecision:
    """Tests for the PreflightDecision dataclass."""

    def test_fields(self) -> None:
        d = PreflightDecision(
            script_name="test-tulla",
            mode="clean",
            source="explicit",
            work_dirs=["./work"],
            remaining_args=["--idea", "42"],
        )
        assert d.script_name == "test-tulla"
        assert d.mode == "clean"
        assert d.source == "explicit"
        assert d.work_dirs == ["./work"]
        assert d.remaining_args == ["--idea", "42"]

    def test_frozen(self) -> None:
        d = PreflightDecision(
            script_name="x",
            mode="clean",
            source="default",
            work_dirs=[],
            remaining_args=[],
        )
        with pytest.raises(AttributeError):
            d.mode = "check"  # type: ignore[misc]

    def test_as_dict(self) -> None:
        d = PreflightDecision(
            script_name="s",
            mode="clean",
            source="default",
            work_dirs=["./w"],
            remaining_args=[],
        )
        result = d.as_dict()
        assert isinstance(result, dict)
        assert result["script_name"] == "s"
        assert result["mode"] == "clean"
        assert result["source"] == "default"
        assert result["work_dirs"] == ["./w"]
        assert result["remaining_args"] == []

    def test_as_json(self) -> None:
        d = PreflightDecision(
            script_name="s",
            mode="check",
            source="explicit",
            work_dirs=[],
            remaining_args=[],
        )
        raw = d.as_json()
        parsed = json.loads(raw)
        assert parsed["mode"] == "check"
        assert parsed["source"] == "explicit"

    def test_as_json_roundtrip(self) -> None:
        d = PreflightDecision(
            script_name="rt",
            mode="no-clean",
            source="explicit",
            work_dirs=["a", "b"],
            remaining_args=["--x"],
        )
        parsed = json.loads(d.as_json())
        assert parsed == d.as_dict()

    def test_equality(self) -> None:
        a = PreflightDecision(
            script_name="s",
            mode="clean",
            source="default",
            work_dirs=[],
            remaining_args=[],
        )
        b = PreflightDecision(
            script_name="s",
            mode="clean",
            source="default",
            work_dirs=[],
            remaining_args=[],
        )
        assert a == b


# ---------------------------------------------------------------------------
# _detect_source
# ---------------------------------------------------------------------------


class TestDetectSource:
    """Tests for source detection logic."""

    def test_explicit_clean_flag(self, clean_config: HygieneConfig) -> None:
        assert _detect_source(clean_config, ["--clean"]) == "explicit"

    def test_explicit_no_clean_flag(self, no_clean_config: HygieneConfig) -> None:
        assert _detect_source(no_clean_config, ["--no-clean"]) == "explicit"

    def test_explicit_check_flag(self, check_config: HygieneConfig) -> None:
        assert _detect_source(check_config, ["--check"]) == "explicit"

    def test_explicit_flag_among_others(self, clean_config: HygieneConfig) -> None:
        assert _detect_source(clean_config, ["--idea", "42", "--clean"]) == "explicit"

    def test_default_when_no_flag(self, clean_config: HygieneConfig) -> None:
        assert _detect_source(clean_config, []) == "default"

    def test_default_with_unrelated_args(self, clean_config: HygieneConfig) -> None:
        assert _detect_source(clean_config, ["--idea", "42"]) == "default"

    def test_unknown_when_argv_none_and_clean(self, clean_config: HygieneConfig) -> None:
        assert _detect_source(clean_config, None) == "unknown"

    def test_explicit_inferred_when_argv_none_and_check(
        self,
        check_config: HygieneConfig,
    ) -> None:
        assert _detect_source(check_config, None) == "explicit"

    def test_explicit_inferred_when_argv_none_and_no_clean(
        self,
        no_clean_config: HygieneConfig,
    ) -> None:
        assert _detect_source(no_clean_config, None) == "explicit"


# ---------------------------------------------------------------------------
# build_preflight_decision
# ---------------------------------------------------------------------------


class TestBuildPreflightDecision:
    """Tests for building a PreflightDecision."""

    def test_basic_clean_mode(
        self,
        clean_config: HygieneConfig,
        work_dirs: list[Path],
    ) -> None:
        d = build_preflight_decision("test", clean_config, work_dirs, argv=["--clean"])
        assert d.script_name == "test"
        assert d.mode == "clean"
        assert d.source == "explicit"
        assert len(d.work_dirs) == 2

    def test_default_mode(
        self,
        clean_config: HygieneConfig,
        work_dirs: list[Path],
    ) -> None:
        d = build_preflight_decision("test", clean_config, work_dirs, argv=[])
        assert d.mode == "clean"
        assert d.source == "default"

    def test_check_mode(
        self,
        check_config: HygieneConfig,
        work_dirs: list[Path],
    ) -> None:
        d = build_preflight_decision("test", check_config, work_dirs, argv=["--check"])
        assert d.mode == "check"
        assert d.source == "explicit"

    def test_no_clean_mode(
        self,
        no_clean_config: HygieneConfig,
        work_dirs: list[Path],
    ) -> None:
        d = build_preflight_decision(
            "test",
            no_clean_config,
            work_dirs,
            argv=["--no-clean"],
        )
        assert d.mode == "no-clean"
        assert d.source == "explicit"

    def test_remaining_args_passthrough(
        self,
        config_with_remaining: HygieneConfig,
        work_dirs: list[Path],
    ) -> None:
        d = build_preflight_decision(
            "test",
            config_with_remaining,
            work_dirs,
            argv=["--clean", "--idea", "42"],
        )
        assert d.remaining_args == ["--idea", "42"]

    def test_work_dirs_serialized_as_strings(
        self,
        clean_config: HygieneConfig,
    ) -> None:
        dirs = [Path("/a/b"), Path("relative/dir")]
        d = build_preflight_decision("test", clean_config, dirs, argv=[])
        assert all(isinstance(w, str) for w in d.work_dirs)
        assert d.work_dirs == ["/a/b", "relative/dir"]

    def test_empty_work_dirs(self, clean_config: HygieneConfig) -> None:
        d = build_preflight_decision("test", clean_config, [], argv=[])
        assert d.work_dirs == []

    def test_argv_none(
        self,
        clean_config: HygieneConfig,
        work_dirs: list[Path],
    ) -> None:
        d = build_preflight_decision("test", clean_config, work_dirs, argv=None)
        assert d.source == "unknown"


# ---------------------------------------------------------------------------
# log_preflight_decision
# ---------------------------------------------------------------------------


class TestLogPreflightDecision:
    """Tests for the main logging entry point."""

    def test_returns_decision(
        self,
        clean_config: HygieneConfig,
        work_dirs: list[Path],
    ) -> None:
        d = log_preflight_decision("test", clean_config, work_dirs, argv=["--clean"])
        assert isinstance(d, PreflightDecision)
        assert d.script_name == "test"

    def test_emits_info_log(
        self,
        clean_config: HygieneConfig,
        work_dirs: list[Path],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="tulla.hygiene.startup_log"):
            log_preflight_decision("my-script", clean_config, work_dirs, argv=["--clean"])
        assert any("Pre-flight decision" in r.message for r in caplog.records)
        assert any("my-script" in r.message for r in caplog.records)
        assert any("mode=clean" in r.message for r in caplog.records)
        assert any("source=explicit" in r.message for r in caplog.records)

    def test_logs_default_source(
        self,
        clean_config: HygieneConfig,
        work_dirs: list[Path],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="tulla.hygiene.startup_log"):
            log_preflight_decision("test", clean_config, work_dirs, argv=[])
        assert any("source=default" in r.message for r in caplog.records)

    def test_logs_check_mode(
        self,
        check_config: HygieneConfig,
        work_dirs: list[Path],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="tulla.hygiene.startup_log"):
            log_preflight_decision("test", check_config, work_dirs, argv=["--check"])
        assert any("mode=check" in r.message for r in caplog.records)

    def test_logs_no_clean_mode(
        self,
        no_clean_config: HygieneConfig,
        work_dirs: list[Path],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="tulla.hygiene.startup_log"):
            log_preflight_decision("test", no_clean_config, work_dirs, argv=["--no-clean"])
        assert any("mode=no-clean" in r.message for r in caplog.records)

    def test_debug_log_for_remaining_args(
        self,
        config_with_remaining: HygieneConfig,
        work_dirs: list[Path],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="tulla.hygiene.startup_log"):
            log_preflight_decision(
                "test",
                config_with_remaining,
                work_dirs,
                argv=["--clean", "--idea", "42"],
            )
        debug_msgs = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        assert any("Remaining args" in m for m in debug_msgs)
        assert any("--idea" in m for m in debug_msgs)

    def test_no_debug_log_without_remaining_args(
        self,
        clean_config: HygieneConfig,
        work_dirs: list[Path],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="tulla.hygiene.startup_log"):
            log_preflight_decision("test", clean_config, work_dirs, argv=["--clean"])
        debug_msgs = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        assert not any("Remaining args" in m for m in debug_msgs)

    def test_decision_matches_returned(
        self,
        clean_config: HygieneConfig,
        work_dirs: list[Path],
    ) -> None:
        d = log_preflight_decision("test", clean_config, work_dirs, argv=["--clean"])
        assert d.mode == clean_config.mode.value
        assert d.work_dirs == [str(w) for w in work_dirs]
