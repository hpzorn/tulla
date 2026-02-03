"""Tests for tulla.ontology.phase_shapes — SHACL Shape Registry."""

from tulla.ontology.phase_shapes import PHASE_SHAPES, get_shape_for_phase


def test_get_shape_for_d5():
    assert get_shape_for_phase("d5") == "phase:D5OutputShape"


def test_get_shape_for_r5():
    assert get_shape_for_phase("r5") == "phase:R5OutputShape"


def test_get_shape_for_p3():
    assert get_shape_for_phase("p3") == "phase:P3OutputShape"


def test_get_shape_for_unknown_phase_returns_none():
    assert get_shape_for_phase("p4") is None


def test_phase_shapes_dict_has_exactly_three_entries():
    assert len(PHASE_SHAPES) == 3
