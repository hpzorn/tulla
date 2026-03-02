"""CI IntentField coverage test (req-73-5-2).

Discovers all Pydantic BaseModel subclasses whose names end in Output or
Result across the tulla package via pkgutil.walk_packages + inspect.getmembers,
then asserts each model has at least one IntentField-annotated field.

Models that intentionally lack IntentField are listed in _EXCEPTIONS.

# @pattern:PortsAndAdapters -- pkgutil.walk_packages discovers models at
#   package boundaries without coupling to specific module paths
# @principle:LooseCoupling -- Test couples only to pydantic.BaseModel and
#   the json_schema_extra marker; no import of specific DxOutput classes
# @principle:SeparationOfConcerns -- Discovery logic
#   (collect_output_result_models) separated from assertion logic (test
#   body); each can evolve independently
# @principle:InformationHiding -- _has_intent_field inspects FieldInfo
#   internals in one place; test cases see only a bool predicate
# @principle:DependencyInversion -- Test depends on the abstract
#   preserves_intent marker convention, not on concrete IntentField or
#   extract_intent_fields callables
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

import pytest
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Exception set — models intentionally exempt from IntentField requirement
# ---------------------------------------------------------------------------

_EXCEPTIONS: set[str] = {
    # Planning outputs P1, P2, P4, P5, P6: pre-73 models; intent annotations
    # deferred until Planning pipeline adopts the A-Box pattern.
    "P1Output",
    "P2Output",
    "P4Output",
    "P5Output",
    "P6Output",
    # Implementation step outputs: operational per-step data, not decision
    # facts.  IterationFactRecord aggregates the intent-carrying subset.
    "FindOutput",
    "ImplementOutput",
    "CommitOutput",
    "VerifyOutput",
    "StatusOutput",
    # Implementation loop-level aggregates: containers for IterationResult
    # and budget tracking, not persisted as A-Box facts.
    "IterationResult",
    "LoopResult",
    # Epistemology outputs: generative idea creation results, not pipeline
    # decision facts.  IntentField adoption tracked separately.
    "EpistemologyOutput",
    # Lightweight pipeline: operational per-step outputs; only
    # LightweightTraceResult carries IntentFields for KG persistence.
    "IntakeOutput",
    "ContextScanOutput",
    "PlanOutput",
    "ExecuteOutput",
}


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def _has_intent_field(model_cls: type[BaseModel]) -> bool:
    """Return True if at least one field has preserves_intent in json_schema_extra."""
    for field_info in model_cls.model_fields.values():
        extra: dict[str, Any] | None = (
            field_info.json_schema_extra
            if isinstance(field_info.json_schema_extra, dict)
            else None
        )
        if extra is not None and extra.get("preserves_intent") is True:
            return True
    return False


def _collect_output_result_models() -> list[type[BaseModel]]:
    """Walk the tulla package and return all BaseModel subclasses named *Output or *Result."""
    import tulla

    models: dict[str, type[BaseModel]] = {}

    for _importer, modname, _ispkg in pkgutil.walk_packages(tulla.__path__, prefix="tulla."):
        try:
            module = importlib.import_module(modname)
        except Exception:
            continue

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseModel)
                and obj is not BaseModel
                and (name.endswith("Output") or name.endswith("Result"))
            ):
                models[name] = obj

    return sorted(models.values(), key=lambda c: c.__name__)


# ---------------------------------------------------------------------------
# Parametrized test
# ---------------------------------------------------------------------------

_MODELS = _collect_output_result_models()


@pytest.mark.parametrize(
    "model_cls",
    _MODELS,
    ids=[m.__name__ for m in _MODELS],
)
def test_model_has_intent_field(model_cls: type[BaseModel]) -> None:
    """Assert that each Output/Result model has at least one IntentField.

    Models listed in _EXCEPTIONS are expected to lack IntentField and are
    skipped with a clear message.
    """
    if model_cls.__name__ in _EXCEPTIONS:
        pytest.skip(f"{model_cls.__name__} is in _EXCEPTIONS (intentionally exempt)")

    assert _has_intent_field(model_cls), (
        f"{model_cls.__name__} (from {model_cls.__module__}) has no field with "
        f"preserves_intent=True in json_schema_extra. Either add an IntentField "
        f"annotation or add the model to _EXCEPTIONS with a comment."
    )
