"""
TDD tests for the visitor demo-feedback system.

POST /api/demo-feedback  — open endpoint: visitors leave feedback on the demo.
GET  /api/demo-feedback  — admin-only: owner reads collected feedback.

Feedback is always persisted to SQLite; if SMTP_* env vars are configured the
message is additionally emailed to FEEDBACK_EMAIL (best-effort, never blocks
or fails the request).

Run: pytest tests/unit/test_demo_feedback.py -v
"""
import pytest

from data import history_store


VALID = {
    "name": "Jane Reviewer",
    "email": "jane@example.com",
    "message": "Impressive demo - the citation verification is a great touch.",
    "rating": 5,
}


class TestSubmitDemoFeedback:
    def test_valid_feedback_returns_200(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(history_store, "_DB_PATH", str(tmp_path / "t.db"))
        resp = client.post("/api/demo-feedback", json=VALID)
        assert resp.status_code == 200
        assert resp.json()["status"] == "received"

    def test_feedback_persisted_to_store(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(history_store, "_DB_PATH", str(tmp_path / "t.db"))
        client.post("/api/demo-feedback", json=VALID)
        import asyncio
        rows = asyncio.run(history_store.get_visitor_feedback())
        assert len(rows) == 1
        assert rows[0]["message"] == VALID["message"]
        assert rows[0]["rating"] == 5

    def test_message_required(self, client):
        resp = client.post("/api/demo-feedback", json={"name": "x", "message": ""})
        assert resp.status_code == 422

    def test_message_too_long_rejected(self, client):
        resp = client.post("/api/demo-feedback", json={"message": "x" * 5001})
        assert resp.status_code == 422

    def test_name_and_email_optional(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(history_store, "_DB_PATH", str(tmp_path / "t.db"))
        resp = client.post("/api/demo-feedback", json={"message": "Anonymous but useful feedback."})
        assert resp.status_code == 200

    def test_invalid_rating_rejected(self, client):
        resp = client.post("/api/demo-feedback", json={"message": "hello there friend", "rating": 9})
        assert resp.status_code == 422

    def test_email_relay_attempted_when_smtp_configured(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(history_store, "_DB_PATH", str(tmp_path / "t.db"))
        from api import routes as routes_module
        sent = {}

        def fake_send(feedback):
            sent.update(feedback)

        monkeypatch.setattr(routes_module, "_send_feedback_email", fake_send)
        client.post("/api/demo-feedback", json=VALID)
        assert sent.get("message") == VALID["message"]

    def test_email_relay_failure_does_not_fail_request(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(history_store, "_DB_PATH", str(tmp_path / "t.db"))
        from api import routes as routes_module

        def boom(feedback):
            raise RuntimeError("SMTP down")

        monkeypatch.setattr(routes_module, "_send_feedback_email", boom)
        resp = client.post("/api/demo-feedback", json=VALID)
        assert resp.status_code == 200


class TestReadDemoFeedback:
    def test_get_requires_admin(self, client):
        resp = client.get("/api/demo-feedback")
        assert resp.status_code in (401, 403)

    def test_get_returns_rows_for_admin(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(history_store, "_DB_PATH", str(tmp_path / "t.db"))
        client.post("/api/demo-feedback", json=VALID)
        token = client.post(
            "/api/auth/token",
            json={"username": "admin", "password": "sentinel123"},
        ).json()["access_token"]
        resp = client.get("/api/demo-feedback", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert body and body[0]["message"] == VALID["message"]
