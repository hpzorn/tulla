"""Tests for tulla.namespaces — central RDF namespace URIs and prefix utilities."""

from __future__ import annotations

from tulla.namespaces import (
    ISAQB_NS,
    PRD_NS,
    PREFIXES,
    REVERSE_PREFIXES,
    TRACE_NS,
    compact_uri,
)


class TestNamespaceConstants:
    """Namespace constants match the expected URIs."""

    def test_prd_ns(self) -> None:
        assert PRD_NS == "http://impl-ralph.io/prd#"

    def test_trace_ns(self) -> None:
        assert TRACE_NS == "http://impl-ralph.io/trace#"

    def test_isaqb_ns(self) -> None:
        assert ISAQB_NS == "http://impl-ralph.io/isaqb#"


class TestPrefixes:
    """PREFIXES maps full URIs to compact prefixes."""

    def test_prd_mapping(self) -> None:
        assert PREFIXES[PRD_NS] == "prd:"

    def test_trace_mapping(self) -> None:
        assert PREFIXES[TRACE_NS] == "trace:"

    def test_isaqb_mapping(self) -> None:
        assert PREFIXES[ISAQB_NS] == "isaqb:"

    def test_rdf_mapping(self) -> None:
        assert PREFIXES["http://www.w3.org/1999/02/22-rdf-syntax-ns#"] == "rdf:"

    def test_rdfs_mapping(self) -> None:
        assert PREFIXES["http://www.w3.org/2000/01/rdf-schema#"] == "rdfs:"

    def test_xsd_mapping(self) -> None:
        assert PREFIXES["http://www.w3.org/2001/XMLSchema#"] == "xsd:"

    def test_six_prefixes(self) -> None:
        assert len(PREFIXES) == 6


class TestReversePrefixes:
    """REVERSE_PREFIXES is the inverse of PREFIXES."""

    def test_roundtrip(self) -> None:
        for full, compact in PREFIXES.items():
            assert REVERSE_PREFIXES[compact] == full

    def test_same_length(self) -> None:
        assert len(REVERSE_PREFIXES) == len(PREFIXES)


class TestCompactUri:
    """compact_uri() compacts full URIs into prefixed form."""

    def test_prd_namespace(self) -> None:
        assert compact_uri("http://impl-ralph.io/prd#Requirement") == "prd:Requirement"

    def test_rdf_namespace(self) -> None:
        assert compact_uri("http://www.w3.org/1999/02/22-rdf-syntax-ns#type") == "rdf:type"

    def test_rdfs_namespace(self) -> None:
        assert compact_uri("http://www.w3.org/2000/01/rdf-schema#label") == "rdfs:label"

    def test_xsd_namespace(self) -> None:
        assert compact_uri("http://www.w3.org/2001/XMLSchema#integer") == "xsd:integer"

    def test_trace_namespace(self) -> None:
        assert compact_uri("http://impl-ralph.io/trace#foo") == "trace:foo"

    def test_isaqb_namespace(self) -> None:
        assert compact_uri("http://impl-ralph.io/isaqb#Maintainability") == "isaqb:Maintainability"

    def test_already_compact(self) -> None:
        assert compact_uri("prd:Requirement") == "prd:Requirement"

    def test_unknown_namespace(self) -> None:
        uri = "http://example.org/unknown#Thing"
        assert compact_uri(uri) == uri
