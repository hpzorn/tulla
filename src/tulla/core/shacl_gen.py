"""SHACL shape generator for IntentField-annotated Pydantic models.

Inspects a BaseModel subclass for IntentField-annotated fields and produces
a Turtle string defining a sh:NodeShape that follows the exact template
used by the existing shapes in phase-ontology.ttl.

Architecture decision: arch:adr-73-2

# @principle:SingleResponsibility -- This module owns only SHACL
#   TTL generation; it does not persist, validate, or query shapes
# @principle:OpenClosedPrinciple -- New phases produce shapes by
#   adding IntentField annotations to their output model; no
#   changes to this generator needed
# @pattern:PipesAndFilters -- generate_shacl_shape transforms a
#   model class into TTL text, acting as a pure filter in the
#   shape-generation pipeline
# @principle:DependencyInversion -- Depends on the abstract
#   IntentField marker (json_schema_extra) rather than concrete
#   model classes or phase_facts
# @principle:LooseCoupling -- Reads only pydantic FieldInfo
#   metadata; no import of any DxOutput model or
#   PhaseFactPersister required
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from tulla.namespaces import PHASE_NS


def generate_shacl_shape(model_cls: type, phase_id: str) -> str:
    """Generate a SHACL NodeShape in Turtle for a Pydantic model's IntentFields.

    Inspects *model_cls* for fields annotated with ``preserves_intent=True``
    (via IntentField) and emits a ``sh:NodeShape`` following the exact template
    used by existing shapes in ``phase-ontology.ttl``.

    Fields whose default is ``None`` are skipped, matching the persist()
    convention (arch:adr-73-4).

    Parameters:
        model_cls: A Pydantic BaseModel subclass to introspect.
        phase_id: The phase identifier (e.g. ``"d5"``), used in the shape
            name, the ``producedBy`` constraint, and the SPARQL target.

    Returns:
        A Turtle string defining the NodeShape, including prefix declarations.

    Raises:
        TypeError: If *model_cls* is not a BaseModel subclass.
    """
    if not (isinstance(model_cls, type) and issubclass(model_cls, BaseModel)):
        raise TypeError(
            f"model_cls must be a BaseModel subclass, got {model_cls!r}"
        )

    # Collect IntentField names, skipping those with default=None
    intent_fields: list[str] = []
    model_fields: dict[str, FieldInfo] = model_cls.model_fields
    for name, field_info in model_fields.items():
        extra = field_info.json_schema_extra
        if not (isinstance(extra, dict) and extra.get("preserves_intent") is True):
            continue
        if field_info.default is None:
            continue
        intent_fields.append(name)

    # Build the shape name from the model class name
    shape_name = f"{model_cls.__name__}Shape"

    # Build property constraints — producedBy first, then each IntentField
    properties: list[str] = []

    # producedBy always gets both minCount and maxCount
    properties.append(
        "[ sh:maxCount 1 ;\n"
        "            sh:minCount 1 ;\n"
        "            sh:path phase:producedBy ]"
    )

    # Each IntentField gets minCount only
    for field_name in intent_fields:
        properties.append(
            "[ sh:minCount 1 ;\n"
            f"            sh:path phase:preserves-{field_name} ]"
        )

    # Join properties with comma-newline separators
    props_str = ",\n        ".join(properties)

    # SPARQL target using full URI for producedBy
    sparql_select = (
        f'SELECT ?this WHERE {{ ?this '
        f'<{PHASE_NS}producedBy> "{phase_id}" . }}'
    )

    # Assemble the full Turtle output
    ttl = (
        f"@prefix phase: <{PHASE_NS}> .\n"
        f"@prefix sh: <http://www.w3.org/ns/shacl#> .\n"
        f"\n"
        f"phase:{shape_name} a sh:NodeShape ;\n"
        f"    sh:property {props_str} ;\n"
        f"    sh:target [ a sh:SPARQLTarget ;\n"
        f'            sh:select "{sparql_select}" ] .\n'
    )

    return ttl
