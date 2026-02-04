"""Tests for tulla.ontology.phase_shapes — SHACL Shape Registry."""

from tulla.namespaces import PHASE_NS
from tulla.ontology.phase_shapes import PHASE_SHAPES, get_shape_for_phase


def test_get_shape_for_d5():
    assert get_shape_for_phase("d5") == f"{PHASE_NS}D5OutputShape"


def test_get_shape_for_r5():
    assert get_shape_for_phase("r5") == f"{PHASE_NS}R5OutputShape"


def test_get_shape_for_p3():
    assert get_shape_for_phase("p3") == f"{PHASE_NS}P3OutputShape"


def test_get_shape_for_unknown_phase_returns_none():
    assert get_shape_for_phase("p4") is None


def test_phase_shapes_dict_has_exactly_four_entries():
    assert len(PHASE_SHAPES) == 4


def test_get_shape_for_lw_trace():
    assert get_shape_for_phase("lw-trace") == f"{PHASE_NS}LWTraceOutputShape"
