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
    """Default adapter pointing at localhost (no env key)."""
    return OntologyMCPAdapter(base_url="http://localhost:8100", api_key="test-key")


def _mock_urlopen(response_data: dict[str, Any] | list) -> MagicMock:
    """Create a mock for urllib.request.urlopen that returns *response_data*."""
    body = json.dumps(response_data).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ===================================================================
# HTTP helper tests
# ===================================================================


class TestHttpHelpers:
    """Tests for _get, _post, _delete helpers."""

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_get_builds_correct_url(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter._get("/facts", {"context": "prd-42", "limit": 10})

        req = mock_urlopen.call_args[0][0]
        assert "http://localhost:8100/facts?" in req.full_url
        assert "context=prd-42" in req.full_url
        assert "limit=10" in req.full_url

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_get_omits_none_params(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter._get("/facts", {"context": "prd-42", "subject": None, "limit": 10})

        req = mock_urlopen.call_args[0][0]
        assert "subject" not in req.full_url

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_post_sends_json_body(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter._post("/facts", {"subject": "s", "predicate": "p", "object": "o"})

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:8100/facts"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent["subject"] == "s"

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_delete_uses_delete_method(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter._delete("/facts/abc-123")

        req = mock_urlopen.call_args[0][0]
        assert req.method == "DELETE"
        assert req.full_url == "http://localhost:8100/facts/abc-123"

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_bearer_auth_header_sent(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({})
        adapter._get("/facts")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer test-key"

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_trailing_slash_stripped_from_base(
        self, mock_urlopen: MagicMock
    ) -> None:
        a = OntologyMCPAdapter(base_url="http://example.com:8080/", api_key="k")
        mock_urlopen.return_value = _mock_urlopen({})
        a._get("/ideas")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://example.com:8080/ideas"


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

        result = adapter._get("/facts")

        assert "error" in result
        assert "Connection refused" in result["error"]

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_url_error_does_not_raise(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.side_effect = URLError("timeout")

        result = adapter._get("/facts")
        assert isinstance(result, dict)


# ===================================================================
# recall_facts() tests
# ===================================================================


class TestRecallFacts:
    """Tests for recall_facts() — GET /facts with response key transform."""

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_uses_get_with_query_params(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"facts": [], "count": 0})
        adapter.recall_facts(subject="x", predicate="y", context="z", limit=10)

        req = mock_urlopen.call_args[0][0]
        assert "/facts?" in req.full_url
        assert "subject=x" in req.full_url
        assert "predicate=y" in req.full_url
        assert "context=z" in req.full_url
        assert "limit=10" in req.full_url
        assert req.data is None  # GET, no body

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_transforms_facts_key_to_result(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen(
            {"facts": [{"subject": "s", "predicate": "p"}], "count": 1}
        )
        result = adapter.recall_facts(context="prd-42")

        assert "result" in result
        assert "facts" not in result
        assert len(result["result"]) == 1


# ===================================================================
# store_fact() tests
# ===================================================================


class TestStoreFact:
    """Tests for store_fact() — POST /facts."""

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_posts_to_facts_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"fact_id": "abc"})
        adapter.store_fact("s", "p", "o", context="ctx", confidence=0.9)

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:8100/facts"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent["subject"] == "s"
        assert sent["predicate"] == "p"
        assert sent["object"] == "o"
        assert sent["context"] == "ctx"
        assert sent["confidence"] == 0.9

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_omits_none_context(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({})
        adapter.store_fact("s", "p", "o")

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert "context" not in sent
        assert sent["confidence"] == 1.0


# ===================================================================
# forget_fact() tests
# ===================================================================


class TestForgetFact:
    """Tests for forget_fact() — DELETE /facts/{fact_id}."""

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_deletes_correct_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"status": "forgotten"})
        adapter.forget_fact("fact-123")

        req = mock_urlopen.call_args[0][0]
        assert req.method == "DELETE"
        assert req.full_url == "http://localhost:8100/facts/fact-123"


# ===================================================================
# query_ideas() tests
# ===================================================================


class TestQueryIdeas:
    """Tests for query_ideas() — GET /ideas with query params."""

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_uses_get_with_limit(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ideas": []})
        adapter.query_ideas()

        req = mock_urlopen.call_args[0][0]
        assert "/ideas?" in req.full_url
        assert "limit=50" in req.full_url
        assert req.data is None  # GET, no body

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_passes_filters_as_query_params(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ideas": []})
        adapter.query_ideas(lifecycle="seed", search="test", limit=10)

        req = mock_urlopen.call_args[0][0]
        assert "lifecycle=seed" in req.full_url
        assert "search=test" in req.full_url
        assert "limit=10" in req.full_url


# ===================================================================
# Other endpoint mapping tests
# ===================================================================


class TestEndpointMapping:
    """Tests for remaining port methods."""

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_get_idea_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"id": "42"})
        adapter.get_idea("42")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:8100/ideas/42"

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_sparql_query_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"bindings": []})
        adapter.sparql_query("SELECT ?s WHERE { ?s ?p ?o }", validate=False)

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:8100/sparql"
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
        assert req.full_url == "http://localhost:8100/ideas/7/update"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"title": "New Title", "tags": ["a", "b"]}

    @patch("ralph.adapters.ontology_mcp.urlopen")
    def test_set_lifecycle_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter.set_lifecycle("5", "active", reason="matured")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:8100/ideas/5/lifecycle"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"new_state": "active", "reason": "matured"}
