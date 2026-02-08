"""Tests for import-graph verification module.

Covers:
- LAYER_RULES — all three structural patterns present
- ImportViolation dataclass — frozen, all required fields
- _extract_imports() — ast-based extraction of import/from-import statements
- _classify_layer() — inner/outer/None classification
- check_import_violations() — main violation checker
- format_violation_report() — human-readable report formatting

Architecture decision tested: arch:adr-65-5
"""

from __future__ import annotations

import textwrap

import pytest

from tulla.phases.implementation.import_graph import (
    LAYER_RULES,
    ImportViolation,
    _classify_layer,
    _extract_imports,
    check_import_violations,
    format_violation_report,
)


# ---------------------------------------------------------------------------
# LAYER_RULES
# ---------------------------------------------------------------------------


class TestLayerRules:
    """LAYER_RULES contains all three structural patterns."""

    def test_all_structural_patterns_present(self) -> None:
        assert "PortsAndAdapters" in LAYER_RULES
        assert "DependencyInversion" in LAYER_RULES
        assert "LayeredArchitecture" in LAYER_RULES

    def test_each_pattern_has_inner_and_outer(self) -> None:
        for pattern_name, rules in LAYER_RULES.items():
            assert "inner" in rules, f"{pattern_name} missing 'inner' layer"
            assert "outer" in rules, f"{pattern_name} missing 'outer' layer"

    def test_inner_and_outer_are_sets(self) -> None:
        for pattern_name, rules in LAYER_RULES.items():
            assert isinstance(rules["inner"], set), f"{pattern_name} inner not a set"
            assert isinstance(rules["outer"], set), f"{pattern_name} outer not a set"

    def test_no_overlap_between_inner_and_outer(self) -> None:
        for pattern_name, rules in LAYER_RULES.items():
            overlap = rules["inner"] & rules["outer"]
            assert not overlap, f"{pattern_name} has overlapping packages: {overlap}"

    def test_only_structural_patterns(self) -> None:
        """arch:adr-65-5: only structural patterns, no behavioral."""
        expected = {"PortsAndAdapters", "DependencyInversion", "LayeredArchitecture"}
        assert set(LAYER_RULES.keys()) == expected


# ---------------------------------------------------------------------------
# ImportViolation dataclass
# ---------------------------------------------------------------------------


class TestImportViolation:
    """ImportViolation is a frozen dataclass with all required fields."""

    def test_fields_present(self) -> None:
        v = ImportViolation(
            file_path="src/core/app.py",
            line_number=5,
            imported_module="tulla.adapters.cli",
            pattern="PortsAndAdapters",
            from_layer="inner",
            to_layer="outer",
            message="violation message",
        )
        assert v.file_path == "src/core/app.py"
        assert v.line_number == 5
        assert v.imported_module == "tulla.adapters.cli"
        assert v.pattern == "PortsAndAdapters"
        assert v.from_layer == "inner"
        assert v.to_layer == "outer"
        assert v.message == "violation message"

    def test_frozen(self) -> None:
        v = ImportViolation(
            file_path="a.py",
            line_number=1,
            imported_module="x",
            pattern="P",
            from_layer="inner",
            to_layer="outer",
        )
        with pytest.raises(AttributeError):
            v.file_path = "b.py"  # type: ignore[misc]

    def test_default_message_empty(self) -> None:
        v = ImportViolation(
            file_path="a.py",
            line_number=1,
            imported_module="x",
            pattern="P",
            from_layer="inner",
            to_layer="outer",
        )
        assert v.message == ""


# ---------------------------------------------------------------------------
# _extract_imports
# ---------------------------------------------------------------------------


class TestExtractImports:
    """_extract_imports uses ast to extract import statements."""

    def test_import_statement(self) -> None:
        source = "import os\nimport sys\n"
        result = _extract_imports(source)
        assert (1, "os") in result
        assert (2, "sys") in result

    def test_from_import_statement(self) -> None:
        source = "from os.path import join\n"
        result = _extract_imports(source)
        assert (1, "os.path") in result

    def test_mixed_imports(self) -> None:
        source = textwrap.dedent("""\
            import os
            from pathlib import Path
            import sys
            from tulla.adapters.cli import main
        """)
        result = _extract_imports(source)
        assert len(result) == 4
        modules = [m for _, m in result]
        assert "os" in modules
        assert "pathlib" in modules
        assert "sys" in modules
        assert "tulla.adapters.cli" in modules

    def test_syntax_error_returns_empty(self) -> None:
        source = "def broken(\n"
        result = _extract_imports(source)
        assert result == []

    def test_empty_source_returns_empty(self) -> None:
        result = _extract_imports("")
        assert result == []

    def test_no_imports_returns_empty(self) -> None:
        source = "x = 1\ny = 2\n"
        result = _extract_imports(source)
        assert result == []

    def test_line_numbers_correct(self) -> None:
        source = "# comment\nimport os\n\nfrom sys import argv\n"
        result = _extract_imports(source)
        assert (2, "os") in result
        assert (4, "sys") in result

    def test_multiple_names_in_import(self) -> None:
        source = "import os, sys, json\n"
        result = _extract_imports(source)
        modules = [m for _, m in result]
        assert "os" in modules
        assert "sys" in modules
        assert "json" in modules


# ---------------------------------------------------------------------------
# _classify_layer
# ---------------------------------------------------------------------------


class TestClassifyLayer:
    """_classify_layer classifies module paths as inner, outer, or None."""

    def test_inner_classification(self) -> None:
        rules = {"inner": {"core", "ports"}, "outer": {"adapters"}}
        assert _classify_layer("tulla.core.model", rules) == "inner"
        assert _classify_layer("tulla.ports.ontology", rules) == "inner"

    def test_outer_classification(self) -> None:
        rules = {"inner": {"core", "ports"}, "outer": {"adapters"}}
        assert _classify_layer("tulla.adapters.cli", rules) == "outer"

    def test_none_for_unrecognised(self) -> None:
        rules = {"inner": {"core"}, "outer": {"adapters"}}
        assert _classify_layer("os.path", rules) is None
        assert _classify_layer("sys", rules) is None

    def test_file_path_with_slashes(self) -> None:
        rules = {"inner": {"core"}, "outer": {"adapters"}}
        assert _classify_layer("tulla/core/model.py", rules) == "inner"
        assert _classify_layer("tulla/adapters/cli.py", rules) == "outer"

    def test_first_matching_segment_wins(self) -> None:
        rules = {"inner": {"core"}, "outer": {"adapters"}}
        # "core" appears before "adapters" in path segments
        assert _classify_layer("tulla.core.adapters.hybrid", rules) == "inner"

    def test_empty_module_path(self) -> None:
        rules = {"inner": {"core"}, "outer": {"adapters"}}
        assert _classify_layer("", rules) is None


# ---------------------------------------------------------------------------
# check_import_violations
# ---------------------------------------------------------------------------


class TestCheckImportViolations:
    """check_import_violations detects inner-to-outer import violations."""

    def test_violation_detected(self) -> None:
        source = textwrap.dedent("""\
            from tulla.adapters.cli import main
        """)
        violations = check_import_violations(
            "src/tulla/core/app.py", source, patterns=["PortsAndAdapters"]
        )
        assert len(violations) == 1
        v = violations[0]
        assert v.file_path == "src/tulla/core/app.py"
        assert v.imported_module == "tulla.adapters.cli"
        assert v.pattern == "PortsAndAdapters"
        assert v.from_layer == "inner"
        assert v.to_layer == "outer"

    def test_no_violation_inner_to_inner(self) -> None:
        source = "from tulla.core.models import Foo\n"
        violations = check_import_violations(
            "src/tulla/ports/ontology.py", source, patterns=["PortsAndAdapters"]
        )
        assert violations == []

    def test_no_violation_outer_to_inner(self) -> None:
        source = "from tulla.core.models import Foo\n"
        violations = check_import_violations(
            "src/tulla/adapters/cli.py", source, patterns=["PortsAndAdapters"]
        )
        assert violations == []

    def test_no_violation_outer_to_outer(self) -> None:
        source = "from tulla.infrastructure.db import connect\n"
        violations = check_import_violations(
            "src/tulla/adapters/cli.py", source, patterns=["PortsAndAdapters"]
        )
        assert violations == []

    def test_defaults_to_all_patterns(self) -> None:
        source = "from tulla.adapters.cli import main\n"
        violations = check_import_violations("src/tulla/core/app.py", source)
        # Should check all three patterns
        patterns_found = {v.pattern for v in violations}
        assert len(patterns_found) >= 1
        # All violations should be for patterns that have "core" as inner
        # and "adapters" as outer
        for v in violations:
            assert v.pattern in LAYER_RULES

    def test_specific_pattern_only(self) -> None:
        source = "from tulla.adapters.cli import main\n"
        violations = check_import_violations(
            "src/tulla/core/app.py", source, patterns=["DependencyInversion"]
        )
        for v in violations:
            assert v.pattern == "DependencyInversion"

    def test_unknown_pattern_ignored(self) -> None:
        source = "from tulla.adapters.cli import main\n"
        violations = check_import_violations(
            "src/tulla/core/app.py", source, patterns=["NonexistentPattern"]
        )
        assert violations == []

    def test_stdlib_imports_no_violation(self) -> None:
        source = "import os\nfrom pathlib import Path\n"
        violations = check_import_violations(
            "src/tulla/core/app.py", source, patterns=["PortsAndAdapters"]
        )
        assert violations == []

    def test_empty_source_no_violation(self) -> None:
        violations = check_import_violations(
            "src/tulla/core/app.py", "", patterns=["PortsAndAdapters"]
        )
        assert violations == []

    def test_syntax_error_no_violation(self) -> None:
        violations = check_import_violations(
            "src/tulla/core/app.py", "def broken(\n", patterns=["PortsAndAdapters"]
        )
        assert violations == []

    def test_file_not_in_inner_layer_no_violation(self) -> None:
        source = "from tulla.adapters.cli import main\n"
        violations = check_import_violations(
            "src/utils/helper.py", source, patterns=["PortsAndAdapters"]
        )
        assert violations == []

    def test_multiple_violations(self) -> None:
        source = textwrap.dedent("""\
            from tulla.adapters.cli import main
            from tulla.infrastructure.db import connect
        """)
        violations = check_import_violations(
            "src/tulla/core/app.py", source, patterns=["PortsAndAdapters"]
        )
        assert len(violations) == 2
        modules = {v.imported_module for v in violations}
        assert "tulla.adapters.cli" in modules
        assert "tulla.infrastructure.db" in modules

    def test_violation_message_populated(self) -> None:
        source = "from tulla.adapters.cli import main\n"
        violations = check_import_violations(
            "src/tulla/core/app.py", source, patterns=["PortsAndAdapters"]
        )
        assert len(violations) == 1
        assert violations[0].message != ""
        assert "PortsAndAdapters" in violations[0].message


# ---------------------------------------------------------------------------
# format_violation_report
# ---------------------------------------------------------------------------


class TestFormatViolationReport:
    """format_violation_report produces human-readable output."""

    def test_no_violations(self) -> None:
        report = format_violation_report([])
        assert report == "No import violations detected."

    def test_single_violation(self) -> None:
        v = ImportViolation(
            file_path="src/core/app.py",
            line_number=5,
            imported_module="tulla.adapters.cli",
            pattern="PortsAndAdapters",
            from_layer="inner",
            to_layer="outer",
            message="test",
        )
        report = format_violation_report([v])
        assert "1 violation" in report
        assert "PortsAndAdapters" in report
        assert "src/core/app.py:5" in report
        assert "tulla.adapters.cli" in report
        assert "inner" in report
        assert "outer" in report

    def test_multiple_violations_grouped_by_pattern(self) -> None:
        v1 = ImportViolation(
            file_path="a.py",
            line_number=1,
            imported_module="adapters.x",
            pattern="PortsAndAdapters",
            from_layer="inner",
            to_layer="outer",
        )
        v2 = ImportViolation(
            file_path="b.py",
            line_number=2,
            imported_module="adapters.y",
            pattern="DependencyInversion",
            from_layer="inner",
            to_layer="outer",
        )
        v3 = ImportViolation(
            file_path="c.py",
            line_number=3,
            imported_module="adapters.z",
            pattern="PortsAndAdapters",
            from_layer="inner",
            to_layer="outer",
        )
        report = format_violation_report([v1, v2, v3])
        assert "3 violations" in report
        # Both patterns appear
        assert "[PortsAndAdapters]" in report
        assert "[DependencyInversion]" in report

    def test_plural_vs_singular(self) -> None:
        v = ImportViolation(
            file_path="a.py",
            line_number=1,
            imported_module="x",
            pattern="P",
            from_layer="inner",
            to_layer="outer",
        )
        report_single = format_violation_report([v])
        assert "1 violation)" in report_single
        report_multi = format_violation_report([v, v])
        assert "2 violations)" in report_multi
