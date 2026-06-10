"""
TDD tests for the View Source endpoint.

GET /api/history/{trace_id}/source → original extracted document text so a
reviewer can verify every citation against the source themselves.

Run: pytest tests/unit/test_source_endpoint.py -v
"""
import pytest

from data import history_store

TRACE = "ab5e713b-e298-4efa-84f8-44cdca93bc0b"


def _record(raw_text="Full extracted document text."):
    return {"trace_id": TRACE, "filename": "contract.pdf", "raw_text": raw_text}


class TestGetSource:
    def test_returns_200_with_raw_text(self, client, monkeypatch):
        async def fake_get(trace_id):
            return _record()
        monkeypatch.setattr(history_store, "get_by_trace_id", fake_get)
        resp = client.get(f"/api/history/{TRACE}/source")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trace_id"] == TRACE
        assert body["filename"] == "contract.pdf"
        assert body["raw_text"] == "Full extracted document text."

    def test_unknown_trace_returns_404(self, client, monkeypatch):
        async def fake_get(trace_id):
            return None
        monkeypatch.setattr(history_store, "get_by_trace_id", fake_get)
        resp = client.get(f"/api/history/{TRACE}/source")
        assert resp.status_code == 404

    def test_record_without_raw_text_returns_404(self, client, monkeypatch):
        async def fake_get(trace_id):
            return _record(raw_text=None)
        monkeypatch.setattr(history_store, "get_by_trace_id", fake_get)
        resp = client.get(f"/api/history/{TRACE}/source")
        assert resp.status_code == 404

    def test_invalid_trace_id_format_returns_422(self, client):
        resp = client.get("/api/history/not-a-uuid/source")
        assert resp.status_code == 422

    def test_response_does_not_leak_other_fields(self, client, monkeypatch):
        async def fake_get(trace_id):
            rec = _record()
            rec["internal_secret"] = "should not appear"
            return rec
        monkeypatch.setattr(history_store, "get_by_trace_id", fake_get)
        resp = client.get(f"/api/history/{TRACE}/source")
        assert "internal_secret" not in resp.json()
