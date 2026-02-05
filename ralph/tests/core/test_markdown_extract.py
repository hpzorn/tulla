"""Tests for extract_rq_sections and extract_field in markdown_extract."""

from __future__ import annotations

from tulla.core.markdown_extract import extract_field, extract_rq_sections


class TestExtractRqSections:
    """Tests for extract_rq_sections."""

    def test_extracts_single_rq(self) -> None:
        content = (
            "## Refined Research Questions\n"
            "\n"
            "### RQ1: How does caching work?\n"
            "**Methodology**: Literature Review\n"
            "**Acceptance Criteria**: Clear answer\n"
        )
        sections = extract_rq_sections(content)
        assert len(sections) == 1
        assert sections[0]["id"] == "RQ1"
        assert sections[0]["title"] == "How does caching work?"
        assert "Literature Review" in sections[0]["body"]

    def test_extracts_multiple_rqs(self) -> None:
        content = (
            "### RQ1: First question\n"
            "Body of RQ1\n"
            "\n"
            "### RQ2: Second question\n"
            "Body of RQ2\n"
            "\n"
            "### RQ3: Third question\n"
            "Body of RQ3\n"
        )
        sections = extract_rq_sections(content)
        assert len(sections) == 3
        assert [s["id"] for s in sections] == ["RQ1", "RQ2", "RQ3"]
        assert [s["title"] for s in sections] == [
            "First question",
            "Second question",
            "Third question",
        ]

    def test_returns_empty_for_no_rqs(self) -> None:
        content = "# Some markdown\n\nNo RQ headings here.\n"
        assert extract_rq_sections(content) == []

    def test_ignores_non_rq_headings(self) -> None:
        content = (
            "### Introduction\n"
            "Some text\n"
            "\n"
            "### RQ1: Actual question\n"
            "Body\n"
            "\n"
            "### Conclusion\n"
            "Final text\n"
        )
        sections = extract_rq_sections(content)
        assert len(sections) == 1
        assert sections[0]["id"] == "RQ1"

    def test_body_stops_at_next_rq(self) -> None:
        content = (
            "### RQ1: First\n"
            "Line 1\n"
            "Line 2\n"
            "### RQ2: Second\n"
            "Line 3\n"
        )
        sections = extract_rq_sections(content)
        assert "Line 1" in sections[0]["body"]
        assert "Line 3" not in sections[0]["body"]
        assert "Line 3" in sections[1]["body"]


class TestExtractField:
    """Tests for extract_field."""

    def test_extracts_simple_field(self) -> None:
        section = "**Status**: Answered\n**Confidence**: High\n"
        assert extract_field(section, "Status") == "Answered"
        assert extract_field(section, "Confidence") == "High"

    def test_returns_empty_when_missing(self) -> None:
        section = "**Status**: Answered\n"
        assert extract_field(section, "Missing") == ""

    def test_handles_multiword_value(self) -> None:
        section = "**Answer**: Use Redis with TTL-based eviction\n"
        assert extract_field(section, "Answer") == "Use Redis with TTL-based eviction"

    def test_handles_special_chars_in_field_name(self) -> None:
        section = "**Acceptance Criteria**: Measurable outcome\n"
        assert extract_field(section, "Acceptance Criteria") == "Measurable outcome"

    def test_strips_whitespace(self) -> None:
        section = "**Status**:   Answered   \n"
        assert extract_field(section, "Status") == "Answered"
