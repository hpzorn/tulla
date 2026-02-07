"""Tests for tulla.core.shacl_gen — SHACL shape generation (req-73-3-4).

Verifies that generate_shacl_shape() produces Turtle output matching the
exact structure of existing shapes in phase-ontology.ttl.  Test cases cover
D5Output, D1Output, optional IntentField handling, and SPARQL target correctness.

# @principle:SeparationOfConcerns -- Shape-generation tests are isolated from persistence and validation tests in test_phase_facts.py; each test class targets one TTL aspect
# @principle:LooseCoupling -- Tests import only generate_shacl_shape and model classes; no dependency on PhaseFactPersister, OntologyPort, or ontology-server
# @principle:DependencyInversion -- Tests verify the generator contract (TTL string output) via string matching, not by importing internal helpers or inspecting FieldInfo
# @principle:InformationHiding -- Inline test models (_OptionalIntentModel equivalent) encapsulate optional-field semantics without exposing generator internals
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from tulla.core.intent import IntentField
from tulla.core.shacl_gen import generate_shacl_shape
from tulla.namespaces import PHASE_NS
from tulla.phases.discovery.models import D1Output, D5Output


class TestGenerateD5Shape:
    """Verify generated D5 shape matches existing D5OutputShape in phase-ontology.ttl."""

    def test_d5_shape_structure(self) -> None:
        """Generated D5 shape must contain all structural elements."""
        ttl = generate_shacl_shape(D5Output, "d5")

        # Prefix declarations
        assert f"@prefix phase: <{PHASE_NS}>" in ttl
        assert "@prefix sh: <http://www.w3.org/ns/shacl#>" in ttl

        # Shape declaration
        assert "phase:D5OutputShape a sh:NodeShape" in ttl

        # producedBy property with maxCount and minCount
        assert "sh:path phase:producedBy" in ttl
        assert "sh:maxCount 1" in ttl

        # IntentField properties
        assert "sh:path phase:preserves-mode" in ttl
        assert "sh:path phase:preserves-recommendation" in ttl

        # SPARQL target
        assert f'<{PHASE_NS}producedBy> "d5"' in ttl

    def test_d5_shape_no_non_intent_fields(self) -> None:
        """Non-IntentField fields (output_file) must NOT appear."""
        ttl = generate_shacl_shape(D5Output, "d5")
        assert "output_file" not in ttl

    def test_d5_exact_property_count(self) -> None:
        """D5 shape must have exactly 6 properties: producedBy + 5 IntentFields."""
        ttl = generate_shacl_shape(D5Output, "d5")
        assert ttl.count("sh:path") == 6


class TestGenerateD1Shape:
    """Verify generated D1 shape includes key_capabilities, ecosystem_context, reuse_opportunities."""

    def test_d1_includes_intent_fields(self) -> None:
        """D1 shape must include preserves-key_capabilities and preserves-ecosystem_context."""
        ttl = generate_shacl_shape(D1Output, "d1")

        assert "phase:D1OutputShape a sh:NodeShape" in ttl
        assert "sh:path phase:preserves-key_capabilities" in ttl
        assert "sh:path phase:preserves-ecosystem_context" in ttl
        assert "sh:path phase:preserves-reuse_opportunities" in ttl

    def test_d1_sparql_target(self) -> None:
        """D1 SPARQL target must reference phase_id d1."""
        ttl = generate_shacl_shape(D1Output, "d1")
        assert f'<{PHASE_NS}producedBy> "d1"' in ttl

    def test_d1_no_inventory_file(self) -> None:
        """Non-IntentField inventory_file must NOT appear in shape."""
        ttl = generate_shacl_shape(D1Output, "d1")
        assert "inventory_file" not in ttl

    def test_d1_exact_property_count(self) -> None:
        """D1 shape must have 4 properties: producedBy + 3 IntentFields."""
        ttl = generate_shacl_shape(D1Output, "d1")
        assert ttl.count("sh:path") == 4


class TestSkipNoneDefaults:
    """Verify fields with default=None are skipped."""

    def test_none_default_field_excluded(self) -> None:
        """IntentField with default=None must not produce a property constraint."""

        class ModelWithOptional(BaseModel):
            required_field: int = IntentField(description="Always present")
            optional_field: str | None = IntentField(
                default=None, description="Sometimes absent"
            )

        ttl = generate_shacl_shape(ModelWithOptional, "test")
        assert "preserves-required_field" in ttl
        assert "optional_field" not in ttl

    def test_all_none_defaults_produces_only_producedby(self) -> None:
        """If all IntentFields default to None, only producedBy remains."""

        class AllOptional(BaseModel):
            opt_a: str | None = IntentField(default=None, description="a")
            opt_b: str | None = IntentField(default=None, description="b")

        ttl = generate_shacl_shape(AllOptional, "test")
        assert ttl.count("sh:path") == 1
        assert "sh:path phase:producedBy" in ttl


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_no_intent_fields(self) -> None:
        """Model with no IntentFields produces shape with only producedBy."""

        class PlainModel(BaseModel):
            some_field: str = "default"
            other_field: int = 0

        ttl = generate_shacl_shape(PlainModel, "plain")
        assert "phase:PlainModelShape a sh:NodeShape" in ttl
        assert ttl.count("sh:path") == 1

    def test_non_basemodel_raises(self) -> None:
        """Passing a non-BaseModel class raises TypeError."""
        with pytest.raises(TypeError, match="BaseModel subclass"):
            generate_shacl_shape(dict, "test")

    def test_non_class_raises(self) -> None:
        """Passing an instance instead of a class raises TypeError."""
        with pytest.raises(TypeError, match="BaseModel subclass"):
            generate_shacl_shape("not a class", "test")  # type: ignore[arg-type]

    def test_mixed_fields(self) -> None:
        """Model with both plain and IntentField-annotated fields."""

        class Mixed(BaseModel):
            path_field: Path = Path(".")
            count: int = IntentField(description="A count")
            name: str = Field(default="x")

        ttl = generate_shacl_shape(Mixed, "mx")
        assert "preserves-count" in ttl
        assert "path_field" not in ttl
        assert "preserves-name" not in ttl


class TestTurtleFormat:
    """Verify the Turtle output format matches the phase-ontology.ttl template."""

    def test_min_count_on_intent_fields(self) -> None:
        """Each IntentField property must have sh:minCount 1."""
        ttl = generate_shacl_shape(D5Output, "d5")
        # Every property block has minCount 1
        lines = ttl.split("\n")
        in_property = False
        property_blocks: list[list[str]] = []
        current_block: list[str] = []
        for line in lines:
            if "sh:path" in line or "sh:minCount" in line or "sh:maxCount" in line:
                current_block.append(line.strip())
            if "]" in line and current_block:
                property_blocks.append(current_block)
                current_block = []

        # All blocks must have minCount 1
        for block in property_blocks:
            block_text = " ".join(block)
            assert "sh:minCount 1" in block_text

    def test_sparql_target_format(self) -> None:
        """SPARQL target must use full URI for producedBy predicate."""
        ttl = generate_shacl_shape(D5Output, "d5")
        expected_select = (
            f'SELECT ?this WHERE {{ ?this '
            f'<{PHASE_NS}producedBy> "d5" . }}'
        )
        assert expected_select in ttl
