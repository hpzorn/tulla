"""Tests for ralph.adapters.ontology_mcp module."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from ralph.adapters.ontology_mcp import OntologyMCPAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def adapter() -> OntologyMCPAdapter:
    """Default adapter pointing at localhost."""
    return OntologyMCPAdapter(base_url="http://localhost:3000")


def _mock_urlopen(response_data: dict[str, Any]) -> MagicMock:
    """Create a mock for urllib.request.urlopen that returns *response_data*."""
    body = json.dumps(response_data).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ===================================================================
# _call() URL and payload construction tests
# ===================================================================


class TestCall:
    """Tests for OntologyMCPAdapter._call() helper."""

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_posts_to_correct_url(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter._call("/api/test", {"key": "value"})

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/api/test"

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_sends_json_payload(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter._call("/api/test", {"foo": "bar", "count": 42})

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"foo": "bar", "count": 42}

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_sets_content_type_json(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({})
        adapter._call("/api/test", {})

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Content-type") == "application/json"

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_returns_parsed_json(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"result": [1, 2, 3]})
        result = adapter._call("/api/test", {})

        assert result == {"result": [1, 2, 3]}

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_trailing_slash_stripped_from_base(
        self, mock_urlopen: MagicMock
    ) -> None:
        a = OntologyMCPAdapter(base_url="http://example.com:8080/")
        mock_urlopen.return_value = _mock_urlopen({})
        a._call("/api/ideas", {})

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://example.com:8080/api/ideas"


# ===================================================================
# Error handling tests
# ===================================================================


class TestErrorHandling:
    """Tests for URLError graceful degradation."""

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_url_error_returns_error_dict(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.side_effect = URLError("Connection refused")

        result = adapter._call("/api/test", {})

        assert "error" in result
        assert "Connection refused" in result["error"]

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_url_error_does_not_raise(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.side_effect = URLError("timeout")

        # Should not raise
        result = adapter._call("/api/test", {})
        assert isinstance(result, dict)


# ===================================================================
# query_ideas() tests
# ===================================================================


class TestQueryIdeas:
    """Tests for query_ideas() endpoint mapping and payload."""

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_default_payload_has_limit(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ideas": []})
        adapter.query_ideas()

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/api/ideas"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"limit": 50}

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_all_filters_included(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ideas": []})
        adapter.query_ideas(
            sparql="SELECT ?s WHERE { ?s ?p ?o }",
            lifecycle="active",
            author="ralph",
            tag="test",
            search="keyword",
            limit=10,
        )

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert sent["sparql"] == "SELECT ?s WHERE { ?s ?p ?o }"
        assert sent["lifecycle"] == "active"
        assert sent["author"] == "ralph"
        assert sent["tag"] == "test"
        assert sent["search"] == "keyword"
        assert sent["limit"] == 10

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_none_filters_omitted(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ideas": []})
        adapter.query_ideas(lifecycle="seed")

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert "sparql" not in sent
        assert "author" not in sent
        assert "tag" not in sent
        assert "search" not in sent
        assert sent["lifecycle"] == "seed"

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_extracts_ideas_from_response(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        expected = {"ideas": [{"id": "1", "title": "Test Idea"}]}
        mock_urlopen.return_value = _mock_urlopen(expected)

        result = adapter.query_ideas(search="test")
        assert result == expected
        assert result["ideas"][0]["title"] == "Test Idea"


# ===================================================================
# Other port method endpoint mapping tests
# ===================================================================


class TestEndpointMapping:
    """Tests that each port method hits the correct REST endpoint."""

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_get_idea_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"id": "42"})
        adapter.get_idea("42")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/api/ideas/42"

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_store_fact_endpoint_and_payload(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"fact_id": "abc"})
        adapter.store_fact("s", "p", "o", context="ctx", confidence=0.9)

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/api/facts"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent["subject"] == "s"
        assert sent["predicate"] == "p"
        assert sent["object"] == "o"
        assert sent["context"] == "ctx"
        assert sent["confidence"] == 0.9

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_store_fact_omits_none_context(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({})
        adapter.store_fact("s", "p", "o")

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert "context" not in sent
        assert sent["confidence"] == 1.0

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_forget_fact_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter.forget_fact("fact-123")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/api/facts/forget"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent["fact_id"] == "fact-123"

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_recall_facts_endpoint_and_payload(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"result": []})
        adapter.recall_facts(subject="x", predicate="y", context="z", limit=10)

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/api/facts/recall"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"subject": "x", "predicate": "y", "context": "z", "limit": 10}

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_sparql_query_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"bindings": []})
        adapter.sparql_query("SELECT ?s WHERE { ?s ?p ?o }", validate=False)

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/api/sparql"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent["query"] == "SELECT ?s WHERE { ?s ?p ?o }"
        assert sent["validate"] is False

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_update_idea_endpoint_and_payload(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter.update_idea("7", title="New Title", tags=["a", "b"])

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/api/ideas/7/update"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"title": "New Title", "tags": ["a", "b"]}

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_update_idea_omits_none_fields(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({})
        adapter.update_idea("7", title="Only Title")

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"title": "Only Title"}

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_set_lifecycle_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter.set_lifecycle("5", "active", reason="matured")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/api/ideas/5/lifecycle"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"new_state": "active", "reason": "matured"}

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_set_lifecycle_omits_empty_reason(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({})
        adapter.set_lifecycle("5", "archived")

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"new_state": "archived"}
