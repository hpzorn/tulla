"""Tests for hygiene help text utilities."""

from ralph.hygiene.help import (
    HYGIENE_HELP_BODY,
    HYGIENE_HELP_HEADER,
    HYGIENE_USAGE_LINE,
    format_hygiene_parser_help,
    get_hygiene_help_text,
    get_hygiene_usage_line,
    inject_hygiene_help,
)


class TestHygieneHelpConstants:
    """Tests for module-level help text constants."""

    def test_usage_line_contains_all_flags(self) -> None:
        assert "--clean" in HYGIENE_USAGE_LINE
        assert "--no-clean" in HYGIENE_USAGE_LINE
        assert "--check" in HYGIENE_USAGE_LINE

    def test_usage_line_shows_mutual_exclusivity(self) -> None:
        assert "|" in HYGIENE_USAGE_LINE

    def test_help_header_value(self) -> None:
        assert HYGIENE_HELP_HEADER == "Hygiene Options:"

    def test_help_body_documents_clean(self) -> None:
        assert "--clean" in HYGIENE_HELP_BODY
        assert "default" in HYGIENE_HELP_BODY.lower()

    def test_help_body_documents_no_clean(self) -> None:
        assert "--no-clean" in HYGIENE_HELP_BODY
        assert "Skip" in HYGIENE_HELP_BODY or "skip" in HYGIENE_HELP_BODY

    def test_help_body_documents_check(self) -> None:
        assert "--check" in HYGIENE_HELP_BODY
        assert "Dry-run" in HYGIENE_HELP_BODY or "dry-run" in HYGIENE_HELP_BODY


class TestGetHygieneHelpText:
    """Tests for get_hygiene_help_text function."""

    def test_includes_header(self) -> None:
        text = get_hygiene_help_text()
        assert HYGIENE_HELP_HEADER in text

    def test_includes_body(self) -> None:
        text = get_hygiene_help_text()
        assert HYGIENE_HELP_BODY in text

    def test_header_before_body(self) -> None:
        text = get_hygiene_help_text()
        header_pos = text.index(HYGIENE_HELP_HEADER)
        body_pos = text.index("--clean")
        assert header_pos < body_pos

    def test_all_three_flags_present(self) -> None:
        text = get_hygiene_help_text()
        assert "--clean" in text
        assert "--no-clean" in text
        assert "--check" in text


class TestGetHygieneUsageLine:
    """Tests for get_hygiene_usage_line function."""

    def test_returns_usage_line(self) -> None:
        assert get_hygiene_usage_line() == HYGIENE_USAGE_LINE

    def test_contains_flags(self) -> None:
        line = get_hygiene_usage_line()
        assert "--clean" in line
        assert "--no-clean" in line
        assert "--check" in line


class TestFormatHygieneParserHelp:
    """Tests for format_hygiene_parser_help function."""

    def test_returns_string(self) -> None:
        result = format_hygiene_parser_help()
        assert isinstance(result, str)

    def test_contains_flag_descriptions(self) -> None:
        result = format_hygiene_parser_help()
        assert "--clean" in result
        assert "--no-clean" in result
        assert "--check" in result

    def test_mentions_default(self) -> None:
        result = format_hygiene_parser_help()
        assert "default" in result.lower()

    def test_mentions_dry_run(self) -> None:
        result = format_hygiene_parser_help()
        assert "dry-run" in result.lower() or "dry run" in result.lower()


class TestInjectHygieneHelp:
    """Tests for inject_hygiene_help function."""

    def test_includes_script_name(self) -> None:
        text = inject_hygiene_help("my-script.sh", "Does something.")
        assert "my-script.sh" in text

    def test_includes_script_description(self) -> None:
        text = inject_hygiene_help("my-script.sh", "Does something.")
        assert "Does something." in text

    def test_includes_hygiene_options_section(self) -> None:
        text = inject_hygiene_help("my-script.sh", "Does something.")
        assert HYGIENE_HELP_HEADER in text

    def test_includes_all_flags(self) -> None:
        text = inject_hygiene_help("research-ralph.sh", "Run research.")
        assert "--clean" in text
        assert "--no-clean" in text
        assert "--check" in text

    def test_usage_line_in_output(self) -> None:
        text = inject_hygiene_help("research-ralph.sh", "Run research.")
        assert "Usage:" in text
        assert HYGIENE_USAGE_LINE.strip() in text

    def test_order_usage_then_description_then_options(self) -> None:
        text = inject_hygiene_help("research-ralph.sh", "Run research rounds.")
        usage_pos = text.index("Usage:")
        desc_pos = text.index("Run research rounds.")
        options_pos = text.index(HYGIENE_HELP_HEADER)
        assert usage_pos < desc_pos < options_pos
