"""Tests for VerifyPhase._build_annotation_verification() prompt section.

Covers:
- TestBuildAnnotationVerification: empty-when-no-patterns, coverage check,
  density check, quality check, structural import check, combined items
- TestVerifyPromptWithAnnotations: prompt contains/excludes
  annotation verification section, section ordering

Architecture decisions tested:
- arch:adr-65-4: Annotation verification as separate _build_ method
- arch:adr-65-5: Import-graph verification for structural patterns only
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.annotations import ANNOTATION_REGEX, APF_TARGET
from tulla.phases.implementation.import_graph import LAYER_RULES
from tulla.phases.implementation.models import FindOutput, ImplementOutput
from tulla.phases.implementation.verify import VerifyPhase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_requirement(**overrides: Any) -> FindOutput:
    defaults = dict(
        requirement_id="prd:req-65-3-2",
        title="Test annotation verification",
        description="Add _build_annotation_verification() to VerifyPhase",
        files=["src/tulla/phases/implementation/verify.py"],
        action="modify",
        verification="pytest tests/",
    )
    defaults.update(overrides)
    return FindOutput(**defaults)


SAMPLE_ARCH_CONTEXT: dict[str, Any] = {
    "quality_goals": ["Correctness: implementation matches spec"],
    "design_principles": [
        "Separation of Concerns: isolated verification prompt building",
    ],
    "adrs": {
        "arch:adr-65-4": "Annotation Section as Separate _build_ Method",
    },
}


# ===================================================================
# TestBuildAnnotationVerification — unit tests
# ===================================================================


class TestBuildAnnotationVerification:
    """Unit tests for VerifyPhase._build_annotation_verification()."""

    # --- empty-when-no-patterns ---

    def test_empty_when_no_resolved_patterns_or_principles(self) -> None:
        req = _make_requirement()
        result = VerifyPhase._build_annotation_verification(req)
        assert result == []

    def test_empty_when_both_lists_explicitly_empty(self) -> None:
        req = _make_requirement(resolved_patterns=[], resolved_principles=[])
        result = VerifyPhase._build_annotation_verification(req)
        assert result == []

    # --- section header ---

    def test_section_header_present(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = VerifyPhase._build_annotation_verification(req)
        assert "## Annotation Verification" in result

    # --- coverage check ---

    def test_coverage_check_header(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "### Coverage Check" in section

    def test_coverage_checklist_contains_all_patterns(self) -> None:
        req = _make_requirement(
            resolved_patterns=["isaqb:LayeredArchitecture", "isaqb:PortsAndAdapters"],
        )
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "- [ ] isaqb:LayeredArchitecture" in section
        assert "- [ ] isaqb:PortsAndAdapters" in section

    def test_coverage_checklist_contains_principles(self) -> None:
        req = _make_requirement(
            resolved_principles=["isaqb:SeparationOfConcerns"],
        )
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "- [ ] isaqb:SeparationOfConcerns" in section

    def test_coverage_includes_format_regex(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert ANNOTATION_REGEX.pattern in section

    def test_combined_checklist_patterns_before_principles(self) -> None:
        req = _make_requirement(
            resolved_patterns=["isaqb:PortsAndAdapters"],
            resolved_principles=["isaqb:DependencyInversion"],
        )
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        pattern_pos = section.index("isaqb:PortsAndAdapters")
        principle_pos = section.index("isaqb:DependencyInversion")
        assert pattern_pos < principle_pos

    # --- density check ---

    def test_density_check_header(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "### Density Check" in section

    def test_density_check_includes_apf_range(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        apf_lo, apf_hi = APF_TARGET
        assert f"{apf_lo}-{apf_hi}" in section
        assert "annotations per file" in section

    # --- quality check ---

    def test_quality_check_header(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "### Quality Check" in section

    def test_quality_check_hollow_detection(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "Hollow" in section
        assert "restates the identifier" in section

    def test_quality_check_verbose_detection(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "Verbose" in section
        assert "50 words" in section

    def test_quality_check_adequate_guidance(self) -> None:
        req = _make_requirement(resolved_patterns=["isaqb:PortsAndAdapters"])
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "adequate" in section
        assert "code-specific" in section

    # --- structural import check ---

    def test_structural_import_check_for_ports_and_adapters(self) -> None:
        req = _make_requirement(
            resolved_patterns=["isaqb:PortsAndAdapters"],
        )
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "### Structural Import Check" in section
        assert "isaqb:PortsAndAdapters" in section
        assert "inner" in section
        assert "outer" in section

    def test_structural_import_check_for_layered_architecture(self) -> None:
        req = _make_requirement(
            resolved_patterns=["isaqb:LayeredArchitecture"],
        )
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "### Structural Import Check" in section
        assert "isaqb:LayeredArchitecture" in section

    def test_structural_import_check_for_dependency_inversion(self) -> None:
        req = _make_requirement(
            resolved_patterns=["isaqb:DependencyInversion"],
        )
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "### Structural Import Check" in section
        assert "isaqb:DependencyInversion" in section

    def test_no_structural_check_for_behavioral_pattern(self) -> None:
        """Behavioral patterns (not in LAYER_RULES) should NOT trigger import check."""
        req = _make_requirement(
            resolved_patterns=["isaqb:CQRS"],
        )
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "### Structural Import Check" not in section

    def test_no_structural_check_for_principles_only(self) -> None:
        """Principles should NOT trigger structural import check."""
        req = _make_requirement(
            resolved_principles=["isaqb:SeparationOfConcerns"],
        )
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "### Structural Import Check" not in section

    def test_structural_check_shows_layer_packages(self) -> None:
        """Layer packages from LAYER_RULES should appear in the import check."""
        req = _make_requirement(
            resolved_patterns=["isaqb:PortsAndAdapters"],
        )
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        rules = LAYER_RULES["PortsAndAdapters"]
        # Check that inner packages are listed
        for pkg in sorted(rules["inner"]):
            assert pkg in section
        # Check that outer packages are listed
        for pkg in sorted(rules["outer"]):
            assert pkg in section

    def test_mixed_structural_and_behavioral(self) -> None:
        """Only structural patterns appear in import check; behavioral excluded."""
        req = _make_requirement(
            resolved_patterns=["isaqb:PortsAndAdapters", "isaqb:CQRS"],
        )
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "### Structural Import Check" in section
        assert "isaqb:PortsAndAdapters" in section
        # CQRS should be in coverage check but NOT in structural import check
        structural_section = section[section.index("### Structural Import Check"):]
        assert "isaqb:CQRS" not in structural_section

    # --- design patterns not included ---

    def test_design_patterns_not_in_checklist(self) -> None:
        """resolved_design_patterns are NOT included in the annotation verification."""
        req = _make_requirement(
            resolved_patterns=["isaqb:PortsAndAdapters"],
            resolved_design_patterns=["GoF:Strategy", "GoF:Observer"],
        )
        result = VerifyPhase._build_annotation_verification(req)
        section = "\n".join(result)
        assert "GoF:Strategy" not in section
        assert "GoF:Observer" not in section

    def test_design_patterns_alone_do_not_trigger_section(self) -> None:
        """Only resolved_design_patterns (no patterns/principles) → empty."""
        req = _make_requirement(
            resolved_design_patterns=["GoF:Strategy"],
        )
        result = VerifyPhase._build_annotation_verification(req)
        assert result == []


# ===================================================================
# TestVerifyPromptWithAnnotations — _build_prompt() integration
# ===================================================================


class TestVerifyPromptWithAnnotations:
    """Tests that _build_prompt() correctly includes/excludes annotation verification."""

    # --- prompt excludes annotation verification ---

    def test_no_annotation_verification_when_no_resolved_items(self) -> None:
        phase = VerifyPhase()
        req = _make_requirement()
        impl = ImplementOutput(
            requirement_id="prd:req-65-3-2",
            files_changed=["src/tulla/phases/implementation/verify.py"],
        )
        prompt = phase._build_prompt(req, impl)
        assert "## Annotation Verification" not in prompt

    def test_no_annotation_verification_with_only_design_patterns(self) -> None:
        phase = VerifyPhase()
        req = _make_requirement(
            resolved_design_patterns=["GoF:Strategy"],
        )
        impl = ImplementOutput(
            requirement_id="prd:req-65-3-2",
            files_changed=["src/tulla/phases/implementation/verify.py"],
        )
        prompt = phase._build_prompt(req, impl)
        assert "## Annotation Verification" not in prompt

    # --- prompt contains annotation verification ---

    def test_annotation_verification_present_with_resolved_patterns(self) -> None:
        phase = VerifyPhase()
        req = _make_requirement(
            resolved_patterns=["isaqb:PortsAndAdapters"],
        )
        impl = ImplementOutput(
            requirement_id="prd:req-65-3-2",
            files_changed=["src/tulla/phases/implementation/verify.py"],
        )
        prompt = phase._build_prompt(req, impl)
        assert "## Annotation Verification" in prompt

    def test_annotation_verification_present_with_resolved_principles(self) -> None:
        phase = VerifyPhase()
        req = _make_requirement(
            resolved_principles=["isaqb:SeparationOfConcerns"],
        )
        impl = ImplementOutput(
            requirement_id="prd:req-65-3-2",
            files_changed=["src/tulla/phases/implementation/verify.py"],
        )
        prompt = phase._build_prompt(req, impl)
        assert "## Annotation Verification" in prompt

    # --- section ordering ---

    def test_annotation_verification_after_architecture_compliance(self) -> None:
        phase = VerifyPhase()
        req = _make_requirement(
            related_adrs=["arch:adr-65-4"],
            quality_focus="isaqb:Correctness",
            resolved_patterns=["isaqb:PortsAndAdapters"],
        )
        impl = ImplementOutput(
            requirement_id="prd:req-65-3-2",
            files_changed=["src/tulla/phases/implementation/verify.py"],
        )
        prompt = phase._build_prompt(req, impl, SAMPLE_ARCH_CONTEXT)
        arch_pos = prompt.index("## Architecture Compliance")
        ann_pos = prompt.index("## Annotation Verification")
        files_pos = prompt.index("## Files to Check")
        assert arch_pos < ann_pos < files_pos

    def test_annotation_verification_before_files_section(self) -> None:
        phase = VerifyPhase()
        req = _make_requirement(
            resolved_patterns=["isaqb:LayeredArchitecture"],
        )
        impl = ImplementOutput(
            requirement_id="prd:req-65-3-2",
            files_changed=["src/tulla/phases/implementation/verify.py"],
        )
        prompt = phase._build_prompt(req, impl)
        ann_pos = prompt.index("## Annotation Verification")
        files_pos = prompt.index("## Files to Check")
        assert ann_pos < files_pos

    def test_annotation_verification_before_instructions(self) -> None:
        phase = VerifyPhase()
        req = _make_requirement(
            resolved_patterns=["isaqb:LayeredArchitecture"],
        )
        impl = ImplementOutput(
            requirement_id="prd:req-65-3-2",
            files_changed=["src/tulla/phases/implementation/verify.py"],
        )
        prompt = phase._build_prompt(req, impl)
        ann_pos = prompt.index("## Annotation Verification")
        instr_pos = prompt.index("## Instructions")
        assert ann_pos < instr_pos

    def test_full_prompt_structure_with_all_sections(self) -> None:
        """All sections present in correct order when all data available."""
        phase = VerifyPhase()
        req = _make_requirement(
            related_adrs=["arch:adr-65-4"],
            quality_focus="isaqb:Correctness",
            resolved_patterns=["isaqb:PortsAndAdapters"],
            resolved_principles=["isaqb:DependencyInversion"],
        )
        impl = ImplementOutput(
            requirement_id="prd:req-65-3-2",
            files_changed=["src/tulla/phases/implementation/verify.py"],
        )
        prompt = phase._build_prompt(req, impl, SAMPLE_ARCH_CONTEXT)

        # Verify all sections exist
        assert "## Requirement:" in prompt
        assert "## Description" in prompt
        assert "## Verification Criteria" in prompt
        assert "## Architecture Compliance" in prompt
        assert "## Annotation Verification" in prompt
        assert "## Files to Check" in prompt
        assert "## Instructions" in prompt
        assert "## Output" in prompt

        # Verify ordering
        sections = [
            "## Requirement:",
            "## Description",
            "## Verification Criteria",
            "## Architecture Compliance",
            "## Annotation Verification",
            "## Files to Check",
            "## Instructions",
            "## Output",
        ]
        positions = [prompt.index(s) for s in sections]
        assert positions == sorted(positions)
