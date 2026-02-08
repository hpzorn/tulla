"""Import-graph verification for structural architecture patterns.

Automated import analysis for PortsAndAdapters, DependencyInversion,
and LayeredArchitecture patterns.  Behavioral patterns are verified
by the LLM-based VerifyPhase instead.

Architecture decision: arch:adr-65-5
Quality focus: isaqb:Correctness
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Layer classification rules per structural pattern
# ---------------------------------------------------------------------------

#: Maps each structural pattern to a dict of ``{layer_name: set_of_packages}``.
#: Packages listed under a layer name are classified as belonging to that layer.
#: The ``"inner"`` layer must NOT import from the ``"outer"`` layer.
LAYER_RULES: dict[str, dict[str, set[str]]] = {
    "PortsAndAdapters": {
        "inner": {"ports", "core", "phases"},
        "outer": {"adapters", "infrastructure", "cli", "commands"},
    },
    "DependencyInversion": {
        "inner": {"ports", "core"},
        "outer": {"adapters", "infrastructure"},
    },
    "LayeredArchitecture": {
        "inner": {"core", "phases", "ports"},
        "outer": {"adapters", "infrastructure", "cli", "commands"},
    },
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImportViolation:
    """A single import direction violation detected in a source file."""

    file_path: str
    """Path to the file containing the violation."""

    line_number: int
    """1-based line number of the offending import statement."""

    imported_module: str
    """The fully-qualified module path that was imported."""

    pattern: str
    """The structural pattern whose layer rule was violated."""

    from_layer: str
    """The layer classification of the file (e.g. ``"inner"``)."""

    to_layer: str
    """The layer classification of the imported module (e.g. ``"outer"``)."""

    message: str = ""
    """Human-readable description of the violation."""


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------


def _extract_imports(source: str) -> list[tuple[int, str]]:
    """Extract all import targets from Python *source* using the ``ast`` module.

    Returns a list of ``(line_number, module_path)`` tuples where
    *line_number* is 1-based and *module_path* is the dotted module
    that is being imported.

    Handles both ``import X`` and ``from X import Y`` forms.
    Returns an empty list if *source* cannot be parsed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.lineno, node.module))
    return imports


# ---------------------------------------------------------------------------
# Layer classification
# ---------------------------------------------------------------------------


def _classify_layer(
    module_path: str,
    layer_rules: dict[str, set[str]],
) -> str | None:
    """Classify a module path as ``"inner"``, ``"outer"``, or ``None``.

    Splits *module_path* by ``.`` and ``/`` separators, strips file
    extensions, and checks each segment against the package sets in
    *layer_rules*.  The first matching segment determines the layer.
    Returns ``None`` if no segment matches any layer.

    Parameters:
        module_path: Dotted Python module path (e.g. ``"tulla.adapters.claude_cli"``)
            or a file path (e.g. ``"tulla/adapters/claude_cli.py"``).
        layer_rules: A dict mapping ``"inner"``/``"outer"`` to sets of
            package-name segments.

    Returns:
        ``"inner"``, ``"outer"``, or ``None``.
    """
    # Normalise: replace '/' with '.', strip .py extension
    normalised = module_path.replace("/", ".").removesuffix(".py")
    parts = normalised.split(".")
    for part in parts:
        for layer_name, packages in layer_rules.items():
            if part in packages:
                return layer_name
    return None


# ---------------------------------------------------------------------------
# Main checker
# ---------------------------------------------------------------------------


def check_import_violations(
    file_path: str,
    source: str,
    patterns: list[str] | None = None,
) -> list[ImportViolation]:
    """Check a source file for import-direction violations.

    Analyses the imports in *source* against :data:`LAYER_RULES` for each
    requested structural pattern.  An import from an ``"inner"`` module to
    an ``"outer"`` module is flagged as a violation.

    Parameters:
        file_path: Path of the source file (used in violation reports).
        source: Python source code to analyse.
        patterns: List of pattern names to check (keys of :data:`LAYER_RULES`).
            If ``None``, all patterns in :data:`LAYER_RULES` are checked.

    Returns:
        A list of :class:`ImportViolation` instances (empty if clean).
    """
    if patterns is None:
        patterns = list(LAYER_RULES.keys())

    imports = _extract_imports(source)
    if not imports:
        return []

    violations: list[ImportViolation] = []

    for pattern_name in patterns:
        layer_rules = LAYER_RULES.get(pattern_name)
        if layer_rules is None:
            continue

        # Classify the file itself
        file_layer = _classify_layer(file_path, layer_rules)
        if file_layer != "inner":
            # Only inner-layer files can violate by importing outer
            continue

        for line_no, module_path in imports:
            target_layer = _classify_layer(module_path, layer_rules)
            if target_layer == "outer":
                violations.append(
                    ImportViolation(
                        file_path=file_path,
                        line_number=line_no,
                        imported_module=module_path,
                        pattern=pattern_name,
                        from_layer="inner",
                        to_layer="outer",
                        message=(
                            f"{pattern_name}: inner module '{file_path}' "
                            f"imports outer module '{module_path}' "
                            f"at line {line_no}"
                        ),
                    )
                )

    return violations


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------


def format_violation_report(violations: list[ImportViolation]) -> str:
    """Format a list of import violations into a human-readable report.

    Parameters:
        violations: List of :class:`ImportViolation` instances.

    Returns:
        A multi-line report string.  Returns a single line confirming
        no violations if the list is empty.
    """
    if not violations:
        return "No import violations detected."

    lines: list[str] = [
        f"Import Violation Report ({len(violations)} violation"
        f"{'s' if len(violations) != 1 else ''})",
        "=" * 60,
    ]

    # Group by pattern
    by_pattern: dict[str, list[ImportViolation]] = {}
    for v in violations:
        by_pattern.setdefault(v.pattern, []).append(v)

    for pattern_name, pattern_violations in sorted(by_pattern.items()):
        lines.append(f"\n[{pattern_name}]")
        for v in pattern_violations:
            lines.append(
                f"  {v.file_path}:{v.line_number} "
                f"imports '{v.imported_module}' "
                f"({v.from_layer} -> {v.to_layer})"
            )

    return "\n".join(lines)
