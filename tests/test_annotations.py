"""Tests for src/tulla/annotations.py — single source of truth for annotation
format, extraction, and quality scoring.

Covers:
- TestAnnotationRegex (Python, TypeScript, quality, ASCII separator, indented,
  malformed rejection)
- TestExtractAnnotations (multiline, empty, no-annotations)
- TestCalculateApf (normal, zero-files, target range)
- TestIsHollow (hollow, adequate)
- TestClassifyAdequacy (adequate, hollow, verbose)

Requirement: prd:req-65-1-5
Quality focus: isaqb:Testability
"""

from tulla.annotations import (
    ANNOTATION_REGEX,
    APF_TARGET,
    Annotation,
    calculate_apf,
    classify_adequacy,
    extract_annotations,
    is_hollow,
)

# ---------------------------------------------------------------------------
# TestAnnotationRegex
# ---------------------------------------------------------------------------


class TestAnnotationRegex:
    """ANNOTATION_REGEX matches valid annotations and rejects malformed ones."""

    def test_python_comment(self):
        m = ANNOTATION_REGEX.match(
            "# @pattern:PortsAndAdapters — OrderService defines abstract port"
        )
        assert m is not None
        assert m.group(1) == "pattern"
        assert m.group(2) == "PortsAndAdapters"
        assert "OrderService" in m.group(3)

    def test_typescript_comment(self):
        m = ANNOTATION_REGEX.match(
            "// @principle:SeparationOfConcerns — validation logic separated from processing"
        )
        assert m is not None
        assert m.group(1) == "principle"
        assert m.group(2) == "SeparationOfConcerns"

    def test_quality_type(self):
        m = ANNOTATION_REGEX.match("# @quality:Testability — pure validation with no side effects")
        assert m is not None
        assert m.group(1) == "quality"
        assert m.group(2) == "Testability"

    def test_ascii_separator(self):
        m = ANNOTATION_REGEX.match("# @pattern:Microservices -- each service owns its data store")
        assert m is not None
        assert m.group(2) == "Microservices"
        assert "data store" in m.group(3)

    def test_indented(self):
        m = ANNOTATION_REGEX.match(
            "    # @principle:DependencyInversion — constructor accepts abstract repo"
        )
        assert m is not None
        assert m.group(1) == "principle"
        assert m.group(2) == "DependencyInversion"

    def test_indented_typescript(self):
        m = ANNOTATION_REGEX.match(
            "  // @quality:Maintainability — isolated filter function, replaceable"
        )
        assert m is not None
        assert m.group(1) == "quality"

    def test_reject_unknown_type(self):
        assert ANNOTATION_REGEX.match("# @unknown:Foo — wrong type") is None

    def test_reject_missing_at_prefix(self):
        assert ANNOTATION_REGEX.match("# pattern:Foo — missing @") is None

    def test_reject_missing_identifier(self):
        assert ANNOTATION_REGEX.match("# @pattern: — missing id") is None

    def test_reject_missing_separator(self):
        assert ANNOTATION_REGEX.match("# @pattern:Foo no separator") is None

    def test_reject_block_comment(self):
        assert ANNOTATION_REGEX.match("/* @pattern:Foo — block */") is None

    def test_reject_no_comment_prefix(self):
        assert ANNOTATION_REGEX.match("@pattern:Foo — bare annotation") is None

    def test_reject_empty_identifier(self):
        assert ANNOTATION_REGEX.match("// @pattern: — empty id") is None


# ---------------------------------------------------------------------------
# TestExtractAnnotations
# ---------------------------------------------------------------------------

MULTILINE_SOURCE = """\
# @pattern:PortsAndAdapters — OrderService defines abstract OrderRepository port
class OrderService:
    def __init__(self, repo):
        # @principle:DependencyInversion — constructor accepts abstract repo
        self._repo = repo

    def place_order(self, order):
        # @quality:Testability — pure validation with no side effects
        self._validate(order)
"""


class TestExtractAnnotations:
    """extract_annotations() returns correct Annotation lists."""

    def test_multiline_extracts_all(self):
        anns = extract_annotations(MULTILINE_SOURCE)
        assert len(anns) == 3
        assert anns[0].ann_type == "pattern"
        assert anns[0].identifier == "PortsAndAdapters"
        assert anns[0].line_number == 1
        assert anns[1].ann_type == "principle"
        assert anns[1].identifier == "DependencyInversion"
        assert anns[1].line_number == 4
        assert anns[2].ann_type == "quality"
        assert anns[2].identifier == "Testability"
        assert anns[2].line_number == 8

    def test_multiline_preserves_explanations(self):
        anns = extract_annotations(MULTILINE_SOURCE)
        assert "OrderService" in anns[0].explanation
        assert "abstract repo" in anns[1].explanation
        assert "pure validation" in anns[2].explanation

    def test_empty_source(self):
        assert extract_annotations("") == []

    def test_no_annotations(self):
        source = "class Foo:\n    pass\n    # just a comment\n"
        assert extract_annotations(source) == []


# ---------------------------------------------------------------------------
# TestCalculateApf
# ---------------------------------------------------------------------------


class TestCalculateApf:
    """calculate_apf() returns correct annotation-per-file counts."""

    def test_normal_count(self):
        anns = extract_annotations(MULTILINE_SOURCE)
        assert calculate_apf(anns) == 3

    def test_zero_files(self):
        assert calculate_apf([]) == 0

    def test_target_range(self):
        anns = extract_annotations(MULTILINE_SOURCE)
        apf = calculate_apf(anns)
        low, high = APF_TARGET
        assert low <= apf <= high


# ---------------------------------------------------------------------------
# TestIsHollow
# ---------------------------------------------------------------------------


class TestIsHollow:
    """is_hollow() detects restated-name explanations vs. code-specific ones."""

    def test_hollow_restates_name(self):
        assert is_hollow("uses the Ports and Adapters pattern", "PortsAndAdapters")

    def test_hollow_applies(self):
        assert is_hollow("applies Separation of Concerns", "SeparationOfConcerns")

    def test_hollow_addresses(self):
        assert is_hollow("addresses testability", "Testability")

    def test_adequate_with_code_specifics(self):
        assert not is_hollow(
            "OrderService defines abstract OrderRepository port; PostgresAdapter implements it",
            "PortsAndAdapters",
        )

    def test_adequate_mechanism_description(self):
        assert not is_hollow(
            "_calculate_granularity_metrics() is a pure data-transform "
            "filter: takes raw requirement blocks, outputs GranularityMetrics "
            "list without side effects",
            "PipesAndFilters",
        )

    def test_adequate_constructor_injection(self):
        assert not is_hollow(
            "constructor accepts abstract repo, not concrete PostgresAdapter",
            "DependencyInversion",
        )


# ---------------------------------------------------------------------------
# TestClassifyAdequacy
# ---------------------------------------------------------------------------


class TestClassifyAdequacy:
    """classify_adequacy() returns 'adequate', 'hollow', or 'verbose'."""

    def test_adequate(self):
        ann = Annotation(
            "pattern",
            "PortsAndAdapters",
            "OrderService defines abstract OrderRepository port; PostgresAdapter implements it",
            1,
        )
        assert classify_adequacy(ann) == "adequate"

    def test_hollow(self):
        ann = Annotation(
            "pattern",
            "PortsAndAdapters",
            "uses the Ports and Adapters pattern",
            1,
        )
        assert classify_adequacy(ann) == "hollow"

    def test_verbose(self):
        verbose_text = (
            "the Ports and Adapters pattern also known as Hexagonal Architecture "
            "was introduced by Alistair Cockburn in 2005 to address coupling between "
            "business logic and infrastructure by defining ports as abstract interfaces "
            "and adapters as concrete implementations that can be swapped at runtime "
            "enabling testing and flexibility in deployment configurations across "
            "different environments and use cases"
        )
        ann = Annotation("pattern", "PortsAndAdapters", verbose_text, 1)
        assert classify_adequacy(ann) == "verbose"

    def test_discriminates_mixed(self):
        adequate_ann = Annotation(
            "pattern",
            "PipesAndFilters",
            "_calculate_granularity_metrics() transforms raw blocks into "
            "GranularityMetrics without side effects or I/O",
            1,
        )
        hollow_ann = Annotation(
            "principle",
            "SeparationOfConcerns",
            "applies Separation of Concerns",
            2,
        )
        assert classify_adequacy(adequate_ann) == "adequate"
        assert classify_adequacy(hollow_ann) == "hollow"
