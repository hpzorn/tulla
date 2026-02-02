"""Tests for ImplementPhase._build_annotation_section() prompt injection.

Covers:
- TestBuildAnnotationSection: empty-when-no-patterns, pattern checklist,
  regex, APF target, good/bad examples, design patterns optional
- TestBuildPromptWithAnnotations: prompt contains/excludes annotation section

Architecture decisions tested:
- arch:adr-65-4: Annotation section as separate _build_ method
- arch:adr-65-6: Class-level annotations by default, APF 2-5
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.annotations import ANNOTATION_REGEX, APF_TARGET
from tulla.phases.implementation.implement import ImplementPhase
from tulla.phases.implementation.models import FindOutput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_requirement(**overrides: Any) -> FindOutput:
    defaults = dict(
        requirement_id="prd:req-65-2-1",
        title="Test annotation section",
        description="Add annotation section to ImplementPhase",
        files=["src/tulla/phases/implementation/implement.py"],
        action="modify",
        verification="pytest tests/",
    )
    defaults.update(overrides)
    return FindOutput(**defaults)


SAMPLE_ARCH_CONTEXT: dict[str, Any] = {
    "quality_goals": ["Correctness: implementation matches spec"],
    "design_principles": [
        "Separation of Concerns: isolated annotation prompt building",
    ],
    "adrs": {
        "arch:adr-65-4": "Annotation Section as Separate _build_ Method",
    },
}


# ===================================================================
# TestBuildAnnotationSection — _build_annotation_section() unit tests
# ===================================================================


class TestBuildAnnotationSection:
    """Unit tests for ImplementPhase._build_annotation_section()."""

    # --- empty-when-no-patterns ---

    def test_empty_when_no_resolved_patterns_or_principles(self) -> None:
        req = _make_requirement()
        result = ImplementPhase._build_annotation_section(req)
        assert result == []

    def test_empty_when_both_lists_explicitly_empty(self) -> None:
        req = _make_requirement(resolved_patterns=[], resolved_principles=[])
        result = ImplementPhase._build_annotation_section(req)
        assert result == []

    # --- pattern checklist ---

    def test_pattern_checklist_contains_all_patterns(self) -> None:
        req = _make_requirement(
            resolved_patterns=["isaqb:LayeredArchitecture", "isaqb:PortsAndAdapters"],
        )
        result = ImplementPhase._build_annotation_section(req)
        section = "\n".join(result)
        assert "**Checklist**" in section
        assert "- [ ] isaqb:LayeredArchitecture" in section
        assert "- [ ] isaqb:PortsAndAdapters" in section

    def test_principle_checklist_items(self) -> None:
        req = _make_requirement(
            resolved_principles=["isaqb:SeparationOfConcerns"],
        )
        result = ImplementPhase._build_annotation_section(req)
        section = "\n".join(result)
        assert "- [ ] isaqb:SeparationOfConcerns" in section

    def test_combined_checklist_patterns_before_principles(self) -> None:
        req = _make_requirement(
            resolved_patterns=["isaqb:PortsAndAdapters"],
            resolved_principles=["isaqb:DependencyInversion"],
        )
        result = ImplementPhase._build_annotation_section(req)
        section = "\n".join(result)
        pattern_pos = section.index("isaqb:PortsAndAdapters")
        principle_pos = section.index("isaqb:DependencyInversion")
        assert pattern_pos < principle_pos

    # --- regex ---

    def test_includes_format_regex(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = ImplementPhase._build_annotation_section(req)
        section = "\n".join(result)
        assert "**Format** (regex):" in section
        assert ANNOTATION_REGEX.pattern in section

    # --- APF target ---

    def test_includes_apf_target_range(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = ImplementPhase._build_annotation_section(req)
        section = "\n".join(result)
        apf_lo, apf_hi = APF_TARGET
        assert f"{apf_lo}-{apf_hi}" in section
        assert "annotations per file" in section

    # --- good/bad examples ---

    def test_includes_good_example(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = ImplementPhase._build_annotation_section(req)
        section = "\n".join(result)
        assert "Good:" in section
        assert "@pattern:PortsAndAdapters" in section
        assert "abstracts" in section

    def test_includes_bad_example(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = ImplementPhase._build_annotation_section(req)
        section = "\n".join(result)
        assert "Bad" in section
        assert "hollow" in section

    # --- design patterns optional ---

    def test_design_patterns_not_in_checklist(self) -> None:
        """resolved_design_patterns are NOT included in the annotation section."""
        req = _make_requirement(
            resolved_patterns=["isaqb:PortsAndAdapters"],
            resolved_design_patterns=["GoF:Strategy", "GoF:Observer"],
        )
        result = ImplementPhase._build_annotation_section(req)
        section = "\n".join(result)
        assert "GoF:Strategy" not in section
        assert "GoF:Observer" not in section

    def test_design_patterns_alone_do_not_trigger_section(self) -> None:
        """Only resolved_design_patterns (no patterns/principles) → empty."""
        req = _make_requirement(
            resolved_design_patterns=["GoF:Strategy"],
        )
        result = ImplementPhase._build_annotation_section(req)
        assert result == []

    # --- section structure ---

    def test_section_header_present(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = ImplementPhase._build_annotation_section(req)
        assert "## Pattern Annotations" in result

    def test_class_level_rule(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = ImplementPhase._build_annotation_section(req)
        section = "\n".join(result)
        assert "class/module level" in section

    def test_explanation_rule(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = ImplementPhase._build_annotation_section(req)
        section = "\n".join(result)
        assert "code-specific detail" in section


# ===================================================================
# TestBuildPromptWithAnnotations — _build_prompt() integration
# ===================================================================


class TestBuildPromptWithAnnotations:
    """Tests that _build_prompt() correctly includes/excludes annotations."""

    # --- prompt excludes annotation section ---

    def test_no_annotation_section_when_no_resolved_items(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement()
        prompt = phase._build_prompt(req, "")
        assert "## Pattern Annotations" not in prompt

    def test_no_annotation_section_with_only_design_patterns(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement(
            resolved_design_patterns=["GoF:Strategy"],
        )
        prompt = phase._build_prompt(req, "")
        assert "## Pattern Annotations" not in prompt

    # --- prompt contains annotation section ---

    def test_annotation_section_present_with_resolved_patterns(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement(
            resolved_patterns=["isaqb:PortsAndAdapters"],
        )
        prompt = phase._build_prompt(req, "")
        assert "## Pattern Annotations" in prompt

    def test_annotation_section_present_with_resolved_principles(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement(
            resolved_principles=["isaqb:SeparationOfConcerns"],
        )
        prompt = phase._build_prompt(req, "")
        assert "## Pattern Annotations" in prompt

    # --- section ordering ---

    def test_annotation_section_after_architecture_context(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement(
            related_adrs=["arch:adr-65-4"],
            quality_focus="isaqb:Correctness",
            resolved_patterns=["isaqb:PortsAndAdapters"],
        )
        prompt = phase._build_prompt(req, "", SAMPLE_ARCH_CONTEXT)
        arch_pos = prompt.index("## Architecture Context")
        ann_pos = prompt.index("## Pattern Annotations")
        files_pos = prompt.index("## Files")
        assert arch_pos < ann_pos < files_pos

    def test_annotation_section_before_files_section(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement(
            resolved_patterns=["isaqb:LayeredArchitecture"],
        )
        prompt = phase._build_prompt(req, "")
        ann_pos = prompt.index("## Pattern Annotations")
        files_pos = prompt.index("## Files")
        assert ann_pos < files_pos

    def test_annotation_section_before_verification(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement(
            resolved_patterns=["isaqb:LayeredArchitecture"],
        )
        prompt = phase._build_prompt(req, "")
        ann_pos = prompt.index("## Pattern Annotations")
        ver_pos = prompt.index("## Verification Criteria")
        assert ann_pos < ver_pos

    def test_full_prompt_structure_with_all_sections(self) -> None:
        """All sections present in correct order when all data available."""
        phase = ImplementPhase()
        req = _make_requirement(
            related_adrs=["arch:adr-65-4"],
            quality_focus="isaqb:Correctness",
            resolved_patterns=["isaqb:PortsAndAdapters"],
            resolved_principles=["isaqb:DependencyInversion"],
        )
        prompt = phase._build_prompt(
            req, "fix the bug",
            SAMPLE_ARCH_CONTEXT,
            lessons=["lesson one"],
        )

        # Verify all sections exist
        assert "## Your Task" in prompt
        assert "## Description" in prompt
        assert "## Architecture Context" in prompt
        assert "## Pattern Annotations" in prompt
        assert "## Files" in prompt
        assert "## Verification Criteria" in prompt
        assert "## Lessons from Previous Requirements" in prompt
        assert "## Previous Attempt Feedback" in prompt
        assert "## Output" in prompt

        # Verify ordering
        sections = [
            "## Your Task",
            "## Description",
            "## Architecture Context",
            "## Pattern Annotations",
            "## Files",
            "## Verification Criteria",
            "## Lessons from Previous Requirements",
            "## Previous Attempt Feedback",
            "## Output",
        ]
        positions = [prompt.index(s) for s in sections]
        assert positions == sorted(positions)
