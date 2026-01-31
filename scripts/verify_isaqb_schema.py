#!/usr/bin/env python3
"""Verify the iSAQB architecture knowledge base is correctly deployed.

Runs verification checks against the ontology-server to confirm:
  1. The isaqb-ontology is loaded with expected triple count
  2. Schema context file exists at prompts/isaqb-schema-context.md
  3. T-Box classes are queryable (DesignPrinciple, QualityAttribute, etc.)
  4. A-Box individuals are populated (design principles, quality attributes, patterns)
  5. Key relationships work (conflictsWith, addresses, embodies)
  6. SHACL shapes are present (ADRShape, QualityScenarioShape, RiskShape)
  7. Cross-ontology properties resolve (isaqb ↔ prd ↔ code namespaces)

PRD Requirement: prd:req-idea-41-2-4 (Task 2.4 — Write Verification Script)
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HOST = os.environ.get("ONTOLOGY_HOST", "localhost")
PORT = int(os.environ.get("ONTOLOGY_PORT", "8100"))
BASE_URL = f"http://{HOST}:{PORT}"

# Project root — scripts/ is one level below
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Expected ontology URI
ISAQB_URI = "ontology://isaqb-ontology"

# Expected triple count range
ISAQB_MIN_TRIPLES = 1200
ISAQB_MAX_TRIPLES = 1500

# Expected T-Box classes (subset — most important)
EXPECTED_CLASSES = [
    "DesignPrinciple",
    "QualityAttribute",
    "QualityScenario",
    "ArchitecturalPattern",
    "DesignPattern",
    "ArchitecturalView",
    "CrossCuttingConcern",
    "ArchitectureDecision",
    "StakeholderRole",
    "Arc42Section",
    "EvaluationMethod",
    "Risk",
    "TechnicalDebt",
]

# Expected A-Box minimum counts
EXPECTED_INDIVIDUALS = {
    "DesignPrinciple": 20,
    "QualityAttribute": 30,
    "ArchitecturalPattern": 10,
    "DesignPattern": 10,
    "CrossCuttingConcern": 12,
    "StakeholderRole": 7,
    "Arc42Section": 11,
    "EvaluationMethod": 4,
}

# Expected SHACL shape names (local part)
EXPECTED_SHAPES = [
    "ADRShape",
    "QualityScenarioShape",
    "RiskShape",
    "QualityGoalShape",
]

# Expected relationship properties
EXPECTED_RELATIONSHIPS = [
    "conflictsWith",
    "addresses",
    "embodies",
    "hasSubAttribute",
    "documentedIn",
]

ISAQB_NS = "http://impl-ralph.io/isaqb#"


@dataclass
class CheckResult:
    """Result of a single verification check."""

    name: str
    passed: bool
    detail: str

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name}: {self.detail}"


def _list_ontologies_http() -> list[dict[str, Any]]:
    """List ontologies via the REST endpoint."""
    req = urllib.request.Request(f"{BASE_URL}/ontologies", method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _query_sparql_http(query: str, ontology_uri: str | None = None) -> list[dict]:
    """Run a SPARQL query via POST /sparql."""
    params: dict[str, str] = {"query": query}
    if ontology_uri:
        params["ontology_uri"] = ontology_uri
    qs = urllib.parse.urlencode(params)
    url = f"{BASE_URL}/sparql?{qs}"
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    if isinstance(body, dict) and "error" in body:
        raise RuntimeError(f"SPARQL error: {body['error']}")
    if isinstance(body, dict) and "results" in body:
        return body["results"]
    return body


def check_ontology_loaded() -> CheckResult:
    """Check 1: isaqb-ontology is loaded with expected triple count."""
    name = "Ontology loaded"
    try:
        ontologies = _list_ontologies_http()
        isaqb = next(
            (o for o in ontologies if o["uri"] == ISAQB_URI),
            None,
        )
        if isaqb is None:
            return CheckResult(name, False, f"{ISAQB_URI} not found in loaded ontologies")

        count = isaqb.get("triple_count", 0)
        if ISAQB_MIN_TRIPLES <= count <= ISAQB_MAX_TRIPLES:
            return CheckResult(
                name, True,
                f"{ISAQB_URI} loaded with {count} triples "
                f"(expected {ISAQB_MIN_TRIPLES}-{ISAQB_MAX_TRIPLES})",
            )
        return CheckResult(
            name, False,
            f"Triple count {count} outside range "
            f"[{ISAQB_MIN_TRIPLES}, {ISAQB_MAX_TRIPLES}]",
        )
    except Exception as exc:
        return CheckResult(name, False, f"Error: {exc}")


def check_schema_context_file() -> CheckResult:
    """Check 2: Schema context file exists and has expected content."""
    name = "Schema context file"
    schema_path = PROJECT_ROOT / "prompts" / "isaqb-schema-context.md"
    try:
        if not schema_path.exists():
            return CheckResult(name, False, f"File not found: {schema_path}")

        content = schema_path.read_text(encoding="utf-8")
        required_sections = [
            "## Namespaces",
            "## T-Box: Classes",
            "## Key Properties",
            "## Example SPARQL Queries",
        ]
        missing = [s for s in required_sections if s not in content]
        if missing:
            return CheckResult(
                name, False,
                f"Missing sections: {', '.join(missing)}",
            )

        size_kb = len(content.encode("utf-8")) / 1024
        return CheckResult(
            name, True,
            f"{schema_path.name} present ({size_kb:.1f} KB) with all expected sections",
        )
    except Exception as exc:
        return CheckResult(name, False, f"Error: {exc}")


def check_tbox_classes() -> CheckResult:
    """Check 3: T-Box classes are queryable."""
    name = "T-Box classes"
    query = f"""
        PREFIX isaqb: <{ISAQB_NS}>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?class WHERE {{
            ?class a owl:Class .
            FILTER(STRSTARTS(STR(?class), "{ISAQB_NS}"))
        }}
    """
    try:
        results = _query_sparql_http(query, ISAQB_URI)
        found_classes = {
            r["class"].replace(ISAQB_NS, "")
            for r in results
            if "class" in r
        }
        missing = [c for c in EXPECTED_CLASSES if c not in found_classes]
        if missing:
            return CheckResult(
                name, False,
                f"Missing classes: {', '.join(missing)} "
                f"(found {len(found_classes)} total)",
            )
        return CheckResult(
            name, True,
            f"All {len(EXPECTED_CLASSES)} expected classes found "
            f"(total: {len(found_classes)})",
        )
    except Exception as exc:
        return CheckResult(name, False, f"Error: {exc}")


def check_abox_individuals() -> CheckResult:
    """Check 4: A-Box individuals are populated with minimum counts."""
    name = "A-Box individuals"
    try:
        short_report: list[str] = []
        failures: list[str] = []

        for class_name, min_count in EXPECTED_INDIVIDUALS.items():
            query = f"""
                PREFIX isaqb: <{ISAQB_NS}>
                SELECT (COUNT(?x) AS ?count) WHERE {{
                    ?x a isaqb:{class_name} .
                }}
            """
            results = _query_sparql_http(query, ISAQB_URI)
            count = int(results[0]["count"]) if results else 0
            if count < min_count:
                failures.append(f"{class_name}: {count} < {min_count}")
            else:
                short_report.append(f"{class_name}={count}")

        if failures:
            return CheckResult(
                name, False,
                f"Below minimum: {'; '.join(failures)}",
            )
        return CheckResult(
            name, True,
            f"All counts meet minimums: {'; '.join(short_report[:4])}...",
        )
    except Exception as exc:
        return CheckResult(name, False, f"Error: {exc}")


def check_relationships() -> CheckResult:
    """Check 5: Key relationships (conflictsWith, addresses, embodies, etc.) work."""
    name = "Key relationships"
    try:
        failures: list[str] = []
        successes: list[str] = []

        for prop in EXPECTED_RELATIONSHIPS:
            query = f"""
                PREFIX isaqb: <{ISAQB_NS}>
                SELECT (COUNT(*) AS ?count) WHERE {{
                    ?s isaqb:{prop} ?o .
                }}
            """
            results = _query_sparql_http(query, ISAQB_URI)
            count = int(results[0]["count"]) if results else 0
            if count == 0:
                failures.append(f"{prop}: 0 triples")
            else:
                successes.append(f"{prop}={count}")

        if failures:
            return CheckResult(
                name, False,
                f"Empty relationships: {'; '.join(failures)}",
            )
        return CheckResult(
            name, True,
            f"All relationships populated: {'; '.join(successes)}",
        )
    except Exception as exc:
        return CheckResult(name, False, f"Error: {exc}")


def check_shacl_shapes() -> CheckResult:
    """Check 6: SHACL shapes are defined in the ontology."""
    name = "SHACL shapes"
    query = f"""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX isaqb: <{ISAQB_NS}>
        SELECT ?shape WHERE {{
            ?shape a sh:NodeShape .
            FILTER(STRSTARTS(STR(?shape), "{ISAQB_NS}"))
        }}
    """
    try:
        results = _query_sparql_http(query, ISAQB_URI)
        found_shapes = {
            r["shape"].replace(ISAQB_NS, "")
            for r in results
            if "shape" in r
        }
        # Match shapes flexibly (prefix match for Strict variants)
        missing: list[str] = []
        for expected in EXPECTED_SHAPES:
            if not any(s.startswith(expected) for s in found_shapes):
                missing.append(expected)

        if missing:
            return CheckResult(
                name, False,
                f"Missing shapes: {', '.join(missing)} "
                f"(found: {', '.join(sorted(found_shapes))})",
            )
        return CheckResult(
            name, True,
            f"All {len(EXPECTED_SHAPES)} expected shapes found: "
            f"{', '.join(sorted(found_shapes))}",
        )
    except Exception as exc:
        return CheckResult(name, False, f"Error: {exc}")


def check_cross_ontology_namespaces() -> CheckResult:
    """Check 7: Cross-ontology properties reference prd: and code: namespaces."""
    name = "Cross-ontology namespaces"
    query = f"""
        PREFIX isaqb: <{ISAQB_NS}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT ?prop ?domain ?range WHERE {{
            ?prop a owl:ObjectProperty .
            FILTER(STRSTARTS(STR(?prop), "{ISAQB_NS}"))
            OPTIONAL {{ ?prop rdfs:domain ?domain }}
            OPTIONAL {{ ?prop rdfs:range ?range }}
            FILTER(
                CONTAINS(STR(COALESCE(?domain, "")), "prd#") ||
                CONTAINS(STR(COALESCE(?domain, "")), "code#") ||
                CONTAINS(STR(COALESCE(?range, "")), "prd#") ||
                CONTAINS(STR(COALESCE(?range, "")), "code#")
            )
        }}
    """
    try:
        results = _query_sparql_http(query, ISAQB_URI)
        if not results:
            return CheckResult(
                name, False,
                "No cross-ontology properties found (expected prd:/code: references)",
            )
        props = [r["prop"].replace(ISAQB_NS, "") for r in results if "prop" in r]
        return CheckResult(
            name, True,
            f"Found {len(results)} cross-ontology properties: "
            f"{', '.join(props[:5])}{'...' if len(props) > 5 else ''}",
        )
    except Exception as exc:
        return CheckResult(name, False, f"Error: {exc}")


def verify_all() -> bool:
    """Run all verification checks. Returns True if all pass."""
    checks = [
        check_ontology_loaded,
        check_schema_context_file,
        check_tbox_classes,
        check_abox_individuals,
        check_relationships,
        check_shacl_shapes,
        check_cross_ontology_namespaces,
    ]

    results: list[CheckResult] = []
    for check_fn in checks:
        result = check_fn()
        results.append(result)
        print(result)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"iSAQB Schema Verification: {passed}/{total} checks passed")

    if passed == total:
        print("ALL CHECKS PASSED — iSAQB schema fully verified.")
        return True
    else:
        failed = [r for r in results if not r.passed]
        print("FAILED CHECKS:")
        for r in failed:
            print(f"  - {r.name}: {r.detail}")
        return False


def main() -> None:
    """Entry point."""
    ok = verify_all()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
