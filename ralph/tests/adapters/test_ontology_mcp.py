"""Tests for tulla.adapters.ontology_mcp module."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from tulla.adapters.ontology_mcp import OntologyMCPAdapter


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
    """Tests for OntologyMCPAdapter._post() / _get() / _delete() helpers."""

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_posts_to_correct_url(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter._post("/test", {"key": "value"})

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/test"

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_sends_json_payload(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter._post("/test", {"foo": "bar", "count": 42})

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"foo": "bar", "count": 42}

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_sets_content_type_json(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({})
        adapter._post("/test", {})

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Content-type") == "application/json"

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_returns_parsed_json(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"result": [1, 2, 3]})
        result = adapter._post("/test", {})

        assert result == {"result": [1, 2, 3]}

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_trailing_slash_stripped_from_base(
        self, mock_urlopen: MagicMock
    ) -> None:
        a = OntologyMCPAdapter(base_url="http://example.com:8080/")
        mock_urlopen.return_value = _mock_urlopen({})
        a._post("/ideas", {})

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://example.com:8080/ideas"


# ===================================================================
# Error handling tests
# ===================================================================


class TestErrorHandling:
    """Tests for URLError graceful degradation."""

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_url_error_returns_error_dict(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.side_effect = URLError("Connection refused")

        result = adapter._post("/test", {})

        assert "error" in result
        assert "Connection refused" in result["error"]

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_url_error_does_not_raise(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.side_effect = URLError("timeout")

        # Should not raise
        result = adapter._post("/test", {})
        assert isinstance(result, dict)


# ===================================================================
# query_ideas() tests
# ===================================================================


class TestQueryIdeas:
    """Tests for query_ideas() endpoint mapping and payload."""

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_default_payload_has_limit(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ideas": []})
        adapter.query_ideas()

        req = mock_urlopen.call_args[0][0]
        # _get sends query params in the URL, limit=50 is always present
        assert "limit=50" in req.full_url
        assert req.full_url.startswith("http://localhost:3000/ideas")

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_all_filters_included(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ideas": []})
        adapter.query_ideas(
            sparql="SELECT ?s WHERE { ?s ?p ?o }",
            lifecycle="active",
            author="tulla",
            tag="test",
            search="keyword",
            limit=10,
        )

        req = mock_urlopen.call_args[0][0]
        url = req.full_url
        # sparql is not sent via query_ideas (it's a kwarg but not in the GET params)
        assert "lifecycle=active" in url
        assert "author=tulla" in url
        assert "tag=test" in url
        assert "search=keyword" in url
        assert "limit=10" in url

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_none_filters_omitted(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ideas": []})
        adapter.query_ideas(lifecycle="seed")

        req = mock_urlopen.call_args[0][0]
        url = req.full_url
        assert "author" not in url
        assert "tag" not in url
        assert "search" not in url
        assert "lifecycle=seed" in url

    @patch("tulla.adapters.ontology_mcp.urlopen")
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

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_get_idea_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"id": "42"})
        adapter.get_idea("42")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/ideas/42"

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_store_fact_endpoint_and_payload(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"fact_id": "abc"})
        adapter.store_fact("s", "p", "o", context="ctx", confidence=0.9)

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/facts"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent["subject"] == "s"
        assert sent["predicate"] == "p"
        assert sent["object"] == "o"
        assert sent["context"] == "ctx"
        assert sent["confidence"] == 0.9

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_store_fact_omits_none_context(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({})
        adapter.store_fact("s", "p", "o")

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert "context" not in sent
        assert sent["confidence"] == 1.0

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_forget_fact_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter.forget_fact("fact-123")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/facts/fact-123"
        assert req.get_method() == "DELETE"

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_recall_facts_endpoint_and_payload(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"result": []})
        adapter.recall_facts(subject="x", predicate="y", context="z", limit=10)

        req = mock_urlopen.call_args[0][0]
        url = req.full_url
        assert url.startswith("http://localhost:3000/facts")
        assert "subject=x" in url
        assert "predicate=y" in url
        assert "context=z" in url
        assert "limit=10" in url

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_sparql_query_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"results": []})
        adapter.sparql_query("SELECT ?s WHERE { ?s ?p ?o }", validate=False)

        req = mock_urlopen.call_args[0][0]
        assert req.full_url.startswith("http://localhost:3000/sparql?query=")
        assert req.get_method() == "POST"
        assert "SELECT" in req.full_url

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_update_idea_endpoint_and_payload(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter.update_idea("7", title="New Title", tags=["a", "b"])

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/ideas/7/update"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"title": "New Title", "tags": ["a", "b"]}

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_update_idea_omits_none_fields(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({})
        adapter.update_idea("7", title="Only Title")

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"title": "Only Title"}

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_set_lifecycle_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"ok": True})
        adapter.set_lifecycle("5", "active", reason="matured")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/ideas/5/lifecycle"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"new_state": "active", "reason": "matured"}

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_set_lifecycle_omits_empty_reason(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({})
        adapter.set_lifecycle("5", "archived")

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"new_state": "archived"}

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_validate_instance_endpoint_and_payload(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"conforms": True})
        adapter.validate_instance(
            "http://example.org/inst/1",
            "http://example.org/shapes/MyShape",
            ontology="http://example.org/onto",
        )

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/validate"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {
            "instance_uri": "http://example.org/inst/1",
            "shape_uri": "http://example.org/shapes/MyShape",
            "ontology": "http://example.org/onto",
        }

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_validate_instance_omits_none_ontology(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"conforms": False})
        adapter.validate_instance(
            "http://example.org/inst/1",
            "http://example.org/shapes/MyShape",
        )

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {
            "instance_uri": "http://example.org/inst/1",
            "shape_uri": "http://example.org/shapes/MyShape",
        }
        assert "ontology" not in sent

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_validate_instance_returns_response(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        expected = {
            "conforms": True,
            "violation_count": 0,
            "violations": [],
            "report": "",
        }
        mock_urlopen.return_value = _mock_urlopen(expected)
        result = adapter.validate_instance(
            "http://example.org/inst/1",
            "http://example.org/shapes/MyShape",
        )
        assert result == expected


# ===================================================================
# forget_by_context() tests
# ===================================================================


class TestForgetByContext:
    """Tests for OntologyMCPAdapter.forget_by_context()."""

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_recalls_then_deletes(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        """Recalls all facts in context, then deletes each by fact_id."""
        recall_resp = _mock_urlopen({
            "facts": [
                {"fact_id": "f1", "subject": "s1"},
                {"fact_id": "f2", "subject": "s2"},
                {"fact_id": "f3", "subject": "s3"},
            ]
        })
        delete_resp = _mock_urlopen({"ok": True})
        mock_urlopen.side_effect = [recall_resp, delete_resp, delete_resp, delete_resp]

        count = adapter.forget_by_context("prd-idea-42")

        assert count == 3
        # First call is the recall GET
        recall_req = mock_urlopen.call_args_list[0][0][0]
        assert "context=prd-idea-42" in recall_req.full_url
        # Next 3 are DELETE calls
        for i in range(1, 4):
            req = mock_urlopen.call_args_list[i][0][0]
            assert req.get_method() == "DELETE"

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_returns_zero_when_no_facts(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"facts": []})

        count = adapter.forget_by_context("empty-context")

        assert count == 0

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_skips_facts_without_id(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        """Facts without fact_id are skipped (not deleted)."""
        recall_resp = _mock_urlopen({
            "facts": [
                {"fact_id": "f1", "subject": "s1"},
                {"subject": "s2"},  # no fact_id
            ]
        })
        delete_resp = _mock_urlopen({"ok": True})
        mock_urlopen.side_effect = [recall_resp, delete_resp]

        count = adapter.forget_by_context("ctx")

        assert count == 1


# ===================================================================
# add_triple() tests
# ===================================================================


class TestAddTriple:
    """Tests for OntologyMCPAdapter.add_triple()."""

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_posts_to_correct_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"status": "added"})
        adapter.add_triple("http://s", "http://p", "http://o")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/ontologies/phase-ontology/triples"

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_sends_spo_payload(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"status": "added"})
        adapter.add_triple("http://s", "http://p", "http://o", is_literal=True)

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {
            "subject": "http://s",
            "predicate": "http://p",
            "object": "http://o",
            "is_literal": True,
        }

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_custom_ontology(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"status": "added"})
        adapter.add_triple("http://s", "http://p", "http://o", ontology="custom-onto")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/ontologies/custom-onto/triples"

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_returns_response(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"status": "added"})
        result = adapter.add_triple("http://s", "http://p", "http://o")
        assert result == {"status": "added"}

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_default_is_literal_false(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"status": "added"})
        adapter.add_triple("http://s", "http://p", "http://o")

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert sent["is_literal"] is False


# ===================================================================
# remove_triples_by_subject() tests
# ===================================================================


class TestRemoveTriplesBySubject:
    """Tests for OntologyMCPAdapter.remove_triples_by_subject()."""

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_posts_to_correct_endpoint(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"removed": 5})
        adapter.remove_triples_by_subject("http://example/s1")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/ontologies/phase-ontology/triples/remove"

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_sends_subject_in_payload(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"removed": 3})
        adapter.remove_triples_by_subject("http://example/s1")

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode("utf-8"))
        assert sent == {"subject": "http://example/s1"}

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_returns_count(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"removed": 7})
        count = adapter.remove_triples_by_subject("http://example/s1")
        assert count == 7

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_returns_zero_on_error(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"error": "not found"})
        count = adapter.remove_triples_by_subject("http://example/missing")
        assert count == 0

    @patch("tulla.adapters.ontology_mcp.urlopen")
    def test_custom_ontology(
        self, mock_urlopen: MagicMock, adapter: OntologyMCPAdapter
    ) -> None:
        mock_urlopen.return_value = _mock_urlopen({"removed": 1})
        adapter.remove_triples_by_subject("http://s", ontology="custom-onto")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:3000/ontologies/custom-onto/triples/remove"
