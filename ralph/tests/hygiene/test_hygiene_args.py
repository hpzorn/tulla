"""Tests for hygiene argument parsing."""

from tulla.hygiene.args import HygieneConfig, HygieneMode, parse_hygiene_args


class TestParseHygieneArgs:
    """Tests for parse_hygiene_args function."""

    def test_default_mode_is_clean(self) -> None:
        config = parse_hygiene_args([])
        assert config.mode == HygieneMode.CLEAN
        assert config.should_clean is True
        assert config.is_check_only is False
        assert config.is_disabled is False

    def test_explicit_clean_flag(self) -> None:
        config = parse_hygiene_args(["--clean"])
        assert config.mode == HygieneMode.CLEAN
        assert config.should_clean is True

    def test_no_clean_flag(self) -> None:
        config = parse_hygiene_args(["--no-clean"])
        assert config.mode == HygieneMode.NO_CLEAN
        assert config.should_clean is False
        assert config.is_disabled is True

    def test_check_flag(self) -> None:
        config = parse_hygiene_args(["--check"])
        assert config.mode == HygieneMode.CHECK
        assert config.is_check_only is True
        assert config.should_clean is False

    def test_remaining_args_passthrough(self) -> None:
        config = parse_hygiene_args(["--clean", "--idea", "42", "--verbose"])
        assert config.mode == HygieneMode.CLEAN
        assert config.remaining_args == ["--idea", "42", "--verbose"]

    def test_no_clean_with_remaining_args(self) -> None:
        config = parse_hygiene_args(["--no-clean", "--rounds", "3"])
        assert config.mode == HygieneMode.NO_CLEAN
        assert config.remaining_args == ["--rounds", "3"]

    def test_check_with_remaining_args(self) -> None:
        config = parse_hygiene_args(["--check", "--idea", "7"])
        assert config.mode == HygieneMode.CHECK
        assert config.remaining_args == ["--idea", "7"]

    def test_hygiene_flag_amid_other_args(self) -> None:
        config = parse_hygiene_args(["--idea", "5", "--check", "--verbose"])
        assert config.mode == HygieneMode.CHECK
        assert config.remaining_args == ["--idea", "5", "--verbose"]

    def test_empty_remaining_when_only_hygiene_flag(self) -> None:
        config = parse_hygiene_args(["--no-clean"])
        assert config.remaining_args == []

    def test_no_args_defaults_clean_empty_remaining(self) -> None:
        config = parse_hygiene_args([])
        assert config.remaining_args == []


class TestHygieneConfig:
    """Tests for HygieneConfig dataclass properties."""

    def test_frozen_dataclass(self) -> None:
        config = HygieneConfig(mode=HygieneMode.CLEAN, remaining_args=[])
        try:
            config.mode = HygieneMode.CHECK  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass

    def test_clean_properties(self) -> None:
        config = HygieneConfig(mode=HygieneMode.CLEAN, remaining_args=[])
        assert config.should_clean is True
        assert config.is_check_only is False
        assert config.is_disabled is False

    def test_no_clean_properties(self) -> None:
        config = HygieneConfig(mode=HygieneMode.NO_CLEAN, remaining_args=[])
        assert config.should_clean is False
        assert config.is_check_only is False
        assert config.is_disabled is True

    def test_check_properties(self) -> None:
        config = HygieneConfig(mode=HygieneMode.CHECK, remaining_args=[])
        assert config.should_clean is False
        assert config.is_check_only is True
        assert config.is_disabled is False


class TestHygieneMode:
    """Tests for HygieneMode enum values."""

    def test_enum_values(self) -> None:
        assert HygieneMode.CLEAN.value == "clean"
        assert HygieneMode.NO_CLEAN.value == "no-clean"
        assert HygieneMode.CHECK.value == "check"

    def test_enum_members(self) -> None:
        assert len(HygieneMode) == 3
