"""
TDD tests for Phase 8E3 — Email Ingestion Endpoint.

POST /api/ingest/email  → accepts JSON {subject, body, tenant_id?}
                         → strips HTML from body
                         → routes through the normal analysis pipeline
                         → returns streaming SSE (same as /api/analyze)

Run: pytest tests/unit/test_email_ingestion.py -v
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch



SAMPLE_EMAIL = {
    "subject": "Contract Review Request",
    "body": "Please review the attached credit agreement.",
    "tenant_id": "default",
}

HTML_EMAIL = {
    "subject": "Contract Review",
    "body": "<html><body><p>Please review the <b>credit agreement</b>.</p></body></html>",
    "tenant_id": "default",
}


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------

class TestEmailIngestionValidation:
    def test_missing_body_returns_422(self, client):
        resp = client.post("/api/ingest/email", json={"subject": "hello"})
        assert resp.status_code == 422

    def test_missing_subject_returns_422(self, client):
        resp = client.post("/api/ingest/email", json={"body": "hello"})
        assert resp.status_code == 422

    def test_empty_body_returns_422(self, client):
        resp = client.post("/api/ingest/email", json={"subject": "hi", "body": ""})
        assert resp.status_code == 422

    def test_body_too_long_returns_422(self, client):
        resp = client.post("/api/ingest/email", json={
            "subject": "hi",
            "body": "x" * (1_000_001),
        })
        assert resp.status_code == 422

    def test_valid_email_returns_200(self, client):
        with patch("api.routes.graph") as mock_graph:
            mock_graph.astream = AsyncMock(return_value=_fake_stream())
            resp = client.post("/api/ingest/email", json=SAMPLE_EMAIL)
        assert resp.status_code == 200

    def test_response_is_event_stream(self, client):
        with patch("api.routes.graph") as mock_graph:
            mock_graph.astream = AsyncMock(return_value=_fake_stream())
            resp = client.post("/api/ingest/email", json=SAMPLE_EMAIL)
        assert "text/event-stream" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# 2. HTML stripping
# ---------------------------------------------------------------------------

class TestHtmlStripping:
    def test_html_tags_stripped_from_body(self):
        from api.email_ingestor import strip_html
        result = strip_html("<p>Hello <b>world</b></p>")
        assert "<" not in result
        assert "Hello" in result
        assert "world" in result

    def test_plain_text_preserved(self):
        from api.email_ingestor import strip_html
        result = strip_html("No HTML here.")
        assert result == "No HTML here."

    def test_html_entities_decoded(self):
        from api.email_ingestor import strip_html
        result = strip_html("&lt;b&gt;bold&lt;/b&gt;")
        assert "&lt;" not in result

    def test_empty_string_returns_empty(self):
        from api.email_ingestor import strip_html
        assert strip_html("") == ""

    def test_only_tags_returns_empty_or_whitespace(self):
        from api.email_ingestor import strip_html
        result = strip_html("<html><body></body></html>")
        assert result.strip() == ""


# ---------------------------------------------------------------------------
# 3. Email body becomes analysis text
# ---------------------------------------------------------------------------

class TestEmailBodyRouting:
    def test_subject_prepended_to_analysis_text(self, client):
        """The analysis text should include the subject so the LLM has full context."""
        captured_states = []

        async def fake_astream(state, **kwargs):
            captured_states.append(state)
            yield {}  # minimal event

        with patch("api.routes.graph") as mock_graph:
            mock_graph.astream = fake_astream
            client.post("/api/ingest/email", json=SAMPLE_EMAIL)

        assert len(captured_states) > 0
        raw_text = captured_states[0].get("raw_text", "")
        assert "Contract Review Request" in raw_text

    def test_html_stripped_before_routing(self, client):
        """Body HTML must be stripped — raw_text should contain plain text."""
        captured_states = []

        async def fake_astream(state, **kwargs):
            captured_states.append(state)
            yield {}

        with patch("api.routes.graph") as mock_graph:
            mock_graph.astream = fake_astream
            client.post("/api/ingest/email", json=HTML_EMAIL)

        raw_text = captured_states[0].get("raw_text", "")
        assert "<html>" not in raw_text
        assert "credit agreement" in raw_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fake_stream():
    yield {
        "router": {
            "doc_type": "CREDIT_AGREEMENT",
            "routing_confidence": 0.9,
            "trace_id": "test-trace",
            "language": "en",
        }
    }
    yield {
        "__end__": {
            "final_decision": "APPROVED",
            "evaluation_score": 0.9,
            "hallucination_risk": "low",
            "clause_results": [],
            "clause_results_history": [],
            "routing_confidence": 0.9,
            "trace_id": "test-trace",
            "language": "en",
            "doc_type": "CREDIT_AGREEMENT",
            "expiry_date": None,
        }
    }
