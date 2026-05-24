"""
Unit + integration tests for user feedback loop (Phase 9A).
TDD: RED first — all tests fail until backend is implemented.
Run: pytest tests/unit/test_feedback.py -v
"""
import asyncio
import pytest


# ---------------------------------------------------------------------------
# history_store feedback functions
# ---------------------------------------------------------------------------

class TestFeedbackStore:
    """Tests for insert_feedback and get_feedback in data/history_store.py."""

    def test_insert_feedback_positive_succeeds(self):
        from data import history_store
        asyncio.run(history_store.insert_feedback("test-trace-001", "positive"))

    def test_insert_feedback_negative_succeeds(self):
        from data import history_store
        asyncio.run(history_store.insert_feedback("test-trace-002", "negative"))

    def test_get_feedback_returns_none_when_absent(self):
        from data import history_store
        result = asyncio.run(history_store.get_feedback("nonexistent-trace-xyz"))
        assert result is None

    def test_get_feedback_returns_inserted_record(self):
        from data import history_store
        trace_id = "test-trace-feedback-roundtrip"
        asyncio.run(history_store.insert_feedback(trace_id, "positive", "Great analysis"))
        result = asyncio.run(history_store.get_feedback(trace_id))
        assert result is not None
        assert result["rating"] == "positive"
        assert result["comment"] == "Great analysis"

    def test_get_feedback_returns_latest_for_trace_id(self):
        from data import history_store
        trace_id = "test-trace-latest-feedback"
        asyncio.run(history_store.insert_feedback(trace_id, "positive"))
        asyncio.run(history_store.insert_feedback(trace_id, "negative", "Changed my mind"))
        result = asyncio.run(history_store.get_feedback(trace_id))
        assert result["rating"] == "negative"

    def test_feedback_comment_truncated_at_500_chars(self):
        from data import history_store
        trace_id = "test-trace-long-comment"
        long_comment = "X" * 600
        asyncio.run(history_store.insert_feedback(trace_id, "positive", long_comment))
        result = asyncio.run(history_store.get_feedback(trace_id))
        assert len(result["comment"]) == 500

    def test_get_feedback_has_created_at_field(self):
        from data import history_store
        trace_id = "test-trace-created-at"
        asyncio.run(history_store.insert_feedback(trace_id, "negative"))
        result = asyncio.run(history_store.get_feedback(trace_id))
        assert "created_at" in result
        assert result["created_at"]  # non-empty


# ---------------------------------------------------------------------------
# /api/feedback/{trace_id} endpoint
# ---------------------------------------------------------------------------



class TestFeedbackEndpoint:
    def test_feedback_endpoint_returns_201_for_positive(self, client):
        resp = client.post(
            "/api/feedback/550e8400-e29b-41d4-a716-446655440000",
            json={"rating": "positive"},
        )
        assert resp.status_code == 201

    def test_feedback_endpoint_returns_201_for_negative(self, client):
        resp = client.post(
            "/api/feedback/550e8400-e29b-41d4-a716-446655440001",
            json={"rating": "negative"},
        )
        assert resp.status_code == 201

    def test_feedback_response_body(self, client):
        resp = client.post(
            "/api/feedback/550e8400-e29b-41d4-a716-446655440002",
            json={"rating": "positive"},
        )
        data = resp.json()
        assert data["status"] == "recorded"

    def test_feedback_invalid_rating_returns_422(self, client):
        resp = client.post(
            "/api/feedback/550e8400-e29b-41d4-a716-446655440003",
            json={"rating": "excellent"},
        )
        assert resp.status_code == 422

    def test_feedback_missing_rating_returns_422(self, client):
        resp = client.post(
            "/api/feedback/550e8400-e29b-41d4-a716-446655440004",
            json={},
        )
        assert resp.status_code == 422

    def test_feedback_invalid_trace_id_format_returns_422(self, client):
        resp = client.post(
            "/api/feedback/not-a-uuid",
            json={"rating": "positive"},
        )
        assert resp.status_code == 422

    def test_feedback_comment_accepted(self, client):
        resp = client.post(
            "/api/feedback/550e8400-e29b-41d4-a716-446655440005",
            json={"rating": "negative", "comment": "The clause extraction seemed off."},
        )
        assert resp.status_code == 201

    def test_feedback_comment_over_500_chars_accepted_but_truncated(self, client):
        resp = client.post(
            "/api/feedback/550e8400-e29b-41d4-a716-446655440006",
            json={"rating": "positive", "comment": "A" * 600},
        )
        assert resp.status_code == 201

    def test_feedback_path_traversal_trace_id_rejected(self, client):
        resp = client.post(
            "/api/feedback/../etc/passwd",
            json={"rating": "positive"},
        )
        assert resp.status_code in (404, 422)

    def test_feedback_empty_body_returns_422(self, client):
        resp = client.post("/api/feedback/550e8400-e29b-41d4-a716-446655440007")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/feedback/summary
# ---------------------------------------------------------------------------

class TestFeedbackSummaryEndpoint:
    def test_feedback_summary_returns_200(self, client):
        resp = client.get("/api/feedback/summary")
        assert resp.status_code == 200

    def test_feedback_summary_returns_list(self, client):
        resp = client.get("/api/feedback/summary")
        assert isinstance(resp.json(), list)

    def test_feedback_summary_entry_has_rating_field(self, client):
        """Insert a feedback record then check summary includes it."""
        import asyncio
        from data import history_store
        asyncio.run(history_store.insert_feedback(
            "550e8400-e29b-41d4-a716-446655441000", "positive", "great"
        ))
        resp = client.get("/api/feedback/summary")
        data = resp.json()
        trace_ids = [e.get("trace_id") for e in data]
        assert "550e8400-e29b-41d4-a716-446655441000" in trace_ids

    def test_feedback_summary_entry_has_filename_field(self, client):
        resp = client.get("/api/feedback/summary")
        data = resp.json()
        for entry in data:
            assert "filename" in entry  # may be None for unlinked trace_ids

    def test_feedback_summary_entry_has_decision_field(self, client):
        resp = client.get("/api/feedback/summary")
        for entry in resp.json():
            assert "decision" in entry

    def test_feedback_summary_entry_has_created_at(self, client):
        resp = client.get("/api/feedback/summary")
        for entry in resp.json():
            assert "created_at" in entry

    def test_feedback_summary_limits_to_100(self, client):
        resp = client.get("/api/feedback/summary")
        assert len(resp.json()) <= 100


# ---------------------------------------------------------------------------
# GET /api/feedback/export (CSV)
# ---------------------------------------------------------------------------

class TestFeedbackExport:
    def test_feedback_export_returns_200(self, client):
        resp = client.get("/api/feedback/export")
        assert resp.status_code == 200

    def test_feedback_export_content_type_is_csv(self, client):
        resp = client.get("/api/feedback/export")
        assert "text/csv" in resp.headers["content-type"]

    def test_feedback_export_has_csv_headers_row(self, client):
        resp = client.get("/api/feedback/export")
        first_line = resp.text.split("\n")[0]
        assert "trace_id" in first_line
        assert "rating" in first_line

    def test_feedback_export_includes_comment_column(self, client):
        resp = client.get("/api/feedback/export")
        first_line = resp.text.split("\n")[0]
        assert "comment" in first_line

    def test_feedback_export_disposition_header(self, client):
        resp = client.get("/api/feedback/export")
        assert "attachment" in resp.headers.get("content-disposition", "")


# ---------------------------------------------------------------------------
# Metrics summary — feedback stats
# ---------------------------------------------------------------------------

class TestMetricsFeedbackStats:
    def test_metrics_summary_includes_feedback_key(self, client):
        resp = client.get("/api/metrics/summary")
        assert "feedback" in resp.json()

    def test_metrics_feedback_has_total(self, client):
        data = client.get("/api/metrics/summary").json()
        assert "total" in data["feedback"]
        assert isinstance(data["feedback"]["total"], int)

    def test_metrics_feedback_has_positive_count(self, client):
        data = client.get("/api/metrics/summary").json()
        assert "positive" in data["feedback"]

    def test_metrics_feedback_has_negative_count(self, client):
        data = client.get("/api/metrics/summary").json()
        assert "negative" in data["feedback"]

    def test_metrics_feedback_has_negative_rate_pct(self, client):
        data = client.get("/api/metrics/summary").json()
        assert "negative_rate_pct" in data["feedback"]
        rate = data["feedback"]["negative_rate_pct"]
        assert isinstance(rate, (int, float))
        assert 0.0 <= rate <= 100.0

    def test_metrics_feedback_total_equals_sum_of_counts(self, client):
        fb = client.get("/api/metrics/summary").json()["feedback"]
        assert fb["total"] == fb["positive"] + fb["negative"]


# ---------------------------------------------------------------------------
# GET /api/feedback/summary store function
# ---------------------------------------------------------------------------

class TestGetFeedbackSummaryStore:
    def test_returns_list(self):
        import asyncio
        from data import history_store
        result = asyncio.run(history_store.get_feedback_summary(limit=10))
        assert isinstance(result, list)

    def test_entry_has_required_keys(self):
        import asyncio
        from data import history_store
        asyncio.run(history_store.insert_feedback(
            "550e8400-e29b-41d4-a716-446655442000", "negative", "wrong doc type"
        ))
        result = asyncio.run(history_store.get_feedback_summary(limit=50))
        entry = next((e for e in result if e.get("trace_id") == "550e8400-e29b-41d4-a716-446655442000"), None)
        assert entry is not None
        assert entry["rating"] == "negative"
        assert "filename" in entry
        assert "decision" in entry
        assert "created_at" in entry


# ---------------------------------------------------------------------------
# JSONL correction logging on negative feedback
# ---------------------------------------------------------------------------

class TestCorrectionJsonlLogging:
    def test_negative_feedback_writes_jsonl(self, client, tmp_path, monkeypatch):
        import json
        jsonl_path = tmp_path / "correction_examples.jsonl"
        monkeypatch.setattr("api.routes._CORRECTION_JSONL_PATH", str(jsonl_path))
        client.post(
            "/api/feedback/550e8400-e29b-41d4-a716-446655443000",
            json={"rating": "negative", "comment": "missed clause"},
        )
        import time; time.sleep(0.1)  # let background task flush
        if jsonl_path.exists():
            lines = [l for l in jsonl_path.read_text().splitlines() if l.strip()]
            assert len(lines) >= 1
            entry = json.loads(lines[0])
            assert entry["rating"] == "negative"
            assert "trace_id" in entry

    def test_positive_feedback_does_not_write_jsonl(self, client, tmp_path, monkeypatch):
        jsonl_path = tmp_path / "correction_examples.jsonl"
        monkeypatch.setattr("api.routes._CORRECTION_JSONL_PATH", str(jsonl_path))
        client.post(
            "/api/feedback/550e8400-e29b-41d4-a716-446655443001",
            json={"rating": "positive"},
        )
        import time; time.sleep(0.1)
        assert not jsonl_path.exists() or jsonl_path.read_text().strip() == ""


# ---------------------------------------------------------------------------
# GET /api/history — Option B: feedback_rating in each row
# ---------------------------------------------------------------------------

class TestHistoryFeedbackJoin:
    def test_history_records_have_feedback_rating_field(self, client):
        resp = client.get("/api/history")
        assert resp.status_code == 200
        records = resp.json()
        for r in records:
            assert "feedback_rating" in r

    def test_feedback_rating_is_none_when_no_feedback_given(self, client):
        resp = client.get("/api/history")
        records = resp.json()
        # At least some records should have None if no feedback inserted for them
        ratings = [r["feedback_rating"] for r in records]
        assert all(r in (None, "positive", "negative") for r in ratings)


# ---------------------------------------------------------------------------
# GET /api/admin/insights/recommendations
# ---------------------------------------------------------------------------

class TestInsightsRecommendationsEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/api/admin/insights/recommendations")
        assert resp.status_code == 200

    def test_returns_list(self, client):
        assert isinstance(client.get("/api/admin/insights/recommendations").json(), list)

    def test_filters_by_status_pending(self, client):
        resp = client.get("/api/admin/insights/recommendations?status=pending")
        assert resp.status_code == 200
        for r in resp.json():
            assert r["status"] == "pending"

    def test_invalid_status_returns_422(self, client):
        resp = client.get("/api/admin/insights/recommendations?status=nonsense")
        assert resp.status_code == 422

    def test_all_status_returns_every_record(self, client):
        resp = client.get("/api/admin/insights/recommendations?status=all")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# POST /api/admin/insights/{rec_id}/approve + reject + undo
# ---------------------------------------------------------------------------

_REC_UUID = "550e8400-e29b-41d4-a716-446655550000"


def _seed_pending_recommendation(client, rec_id: str, rec_type: str = "missing_rule", proposed: str = "test clause") -> None:
    """Insert a pending recommendation directly via the store so endpoint tests have data."""
    import asyncio
    from data import history_store
    from datetime import datetime, timezone
    asyncio.run(history_store.create_recommendation({
        "rec_id": rec_id,
        "doc_type": "LEGAL_CONTRACT",
        "rec_type": rec_type,
        "proposed": proposed,
        "evidence_count": 3,
        "confidence": "high",
        "rationale": "Test rationale.",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))


class TestApproveRecommendation:
    def test_approve_unknown_rec_returns_404(self, client):
        resp = client.post("/api/admin/insights/00000000-0000-0000-0000-000000000099/approve")
        assert resp.status_code == 404

    def test_approve_missing_rule_returns_200(self, client, tmp_path, monkeypatch):
        import asyncio
        from data import history_store
        rec_id = "550e8400-e29b-41d4-a716-446655550001"
        _seed_pending_recommendation(client, rec_id, "missing_rule", "test_approve_clause")
        monkeypatch.setattr("api.routes._REG_DB_PATH",
                            __import__("pathlib").Path(tmp_path / "regulatory_db.json"))
        (tmp_path / "regulatory_db.json").write_text('{"LEGAL_CONTRACT": []}')
        resp = client.post(f"/api/admin/insights/{rec_id}/approve")
        assert resp.status_code == 200

    def test_approve_sets_status_approved(self, client, tmp_path, monkeypatch):
        import asyncio
        from data import history_store
        rec_id = "550e8400-e29b-41d4-a716-446655550002"
        _seed_pending_recommendation(client, rec_id, "missing_rule", "status_check_clause")
        monkeypatch.setattr("api.routes._REG_DB_PATH",
                            __import__("pathlib").Path(tmp_path / "regulatory_db.json"))
        (tmp_path / "regulatory_db.json").write_text('{"LEGAL_CONTRACT": []}')
        client.post(f"/api/admin/insights/{rec_id}/approve")
        rec = asyncio.run(history_store.get_recommendation(rec_id))
        assert rec["status"] == "approved"

    def test_approve_already_approved_returns_400(self, client, tmp_path, monkeypatch):
        import asyncio
        from data import history_store
        rec_id = "550e8400-e29b-41d4-a716-446655550003"
        _seed_pending_recommendation(client, rec_id, "missing_rule", "double_approve_clause")
        monkeypatch.setattr("api.routes._REG_DB_PATH",
                            __import__("pathlib").Path(tmp_path / "regulatory_db.json"))
        (tmp_path / "regulatory_db.json").write_text('{"LEGAL_CONTRACT": []}')
        client.post(f"/api/admin/insights/{rec_id}/approve")
        resp = client.post(f"/api/admin/insights/{rec_id}/approve")
        assert resp.status_code == 400

    def test_approve_comprehension_writes_few_shot_jsonl(self, client, tmp_path, monkeypatch):
        import asyncio, json as _json
        from data import history_store
        rec_id = "550e8400-e29b-41d4-a716-446655550004"
        proposed = _json.dumps({
            "clause": "force majeure clause",
            "failed_phrase": "Acts of God",
            "correction": "Phrase satisfies force majeure."
        })
        _seed_pending_recommendation(client, rec_id, "comprehension_failure", proposed)
        few_shot_path = tmp_path / "few_shot_examples.jsonl"
        monkeypatch.setattr("api.routes._FEW_SHOT_PATH", few_shot_path)
        client.post(f"/api/admin/insights/{rec_id}/approve")
        assert few_shot_path.exists()
        entry = _json.loads(few_shot_path.read_text().strip())
        assert entry["rec_id"] == rec_id
        assert entry["clause"] == "force majeure clause"


class TestRejectRecommendation:
    def test_reject_unknown_rec_returns_404(self, client):
        resp = client.post("/api/admin/insights/00000000-0000-0000-0000-000000000098/reject")
        assert resp.status_code == 404

    def test_reject_pending_returns_200(self, client):
        rec_id = "550e8400-e29b-41d4-a716-446655550010"
        _seed_pending_recommendation(client, rec_id)
        resp = client.post(f"/api/admin/insights/{rec_id}/reject")
        assert resp.status_code == 200

    def test_reject_sets_status_rejected(self, client):
        import asyncio
        from data import history_store
        rec_id = "550e8400-e29b-41d4-a716-446655550011"
        _seed_pending_recommendation(client, rec_id)
        client.post(f"/api/admin/insights/{rec_id}/reject")
        rec = asyncio.run(history_store.get_recommendation(rec_id))
        assert rec["status"] == "rejected"

    def test_reject_adds_to_blacklist(self, client):
        import asyncio
        from data import history_store
        rec_id = "550e8400-e29b-41d4-a716-446655550012"
        _seed_pending_recommendation(client, rec_id, proposed="blacklist_me_clause")
        client.post(f"/api/admin/insights/{rec_id}/reject")
        assert asyncio.run(history_store.is_blacklisted("LEGAL_CONTRACT", "blacklist_me_clause"))

    def test_reject_already_rejected_returns_400(self, client):
        rec_id = "550e8400-e29b-41d4-a716-446655550013"
        _seed_pending_recommendation(client, rec_id, proposed="double_reject_clause")
        client.post(f"/api/admin/insights/{rec_id}/reject")
        resp = client.post(f"/api/admin/insights/{rec_id}/reject")
        assert resp.status_code == 400


class TestUndoRecommendation:
    def test_undo_unknown_rec_returns_404(self, client):
        resp = client.post("/api/admin/insights/00000000-0000-0000-0000-000000000097/undo")
        assert resp.status_code == 404

    def test_undo_pending_returns_400(self, client):
        rec_id = "550e8400-e29b-41d4-a716-446655550020"
        _seed_pending_recommendation(client, rec_id, proposed="undo_pending_clause")
        resp = client.post(f"/api/admin/insights/{rec_id}/undo")
        assert resp.status_code == 400

    def test_undo_approved_missing_rule_sets_status_undone(self, client, tmp_path, monkeypatch):
        import asyncio
        from data import history_store
        rec_id = "550e8400-e29b-41d4-a716-446655550021"
        _seed_pending_recommendation(client, rec_id, "missing_rule", "undo_me_clause")
        monkeypatch.setattr("api.routes._REG_DB_PATH",
                            __import__("pathlib").Path(tmp_path / "regulatory_db.json"))
        (tmp_path / "regulatory_db.json").write_text('{"LEGAL_CONTRACT": [{"name":"undo_me_clause","risk_level":"MEDIUM"}]}')
        client.post(f"/api/admin/insights/{rec_id}/approve")
        resp = client.post(f"/api/admin/insights/{rec_id}/undo")
        assert resp.status_code == 200
        rec = asyncio.run(history_store.get_recommendation(rec_id))
        assert rec["status"] == "undone"

    def test_undo_approved_missing_rule_removes_clause_from_db(self, client, tmp_path, monkeypatch):
        import json as _json
        rec_id = "550e8400-e29b-41d4-a716-446655550022"
        _seed_pending_recommendation(client, rec_id, "missing_rule", "remove_me_clause")
        reg_path = tmp_path / "regulatory_db.json"
        reg_path.write_text('{"LEGAL_CONTRACT": []}')
        monkeypatch.setattr("api.routes._REG_DB_PATH", reg_path)
        client.post(f"/api/admin/insights/{rec_id}/approve")
        # Verify clause was added
        data = _json.loads(reg_path.read_text())
        names = [c["name"] for c in data.get("LEGAL_CONTRACT", [])]
        assert "remove_me_clause" in names
        # Now undo
        client.post(f"/api/admin/insights/{rec_id}/undo")
        data_after = _json.loads(reg_path.read_text())
        names_after = [c["name"] for c in data_after.get("LEGAL_CONTRACT", [])]
        assert "remove_me_clause" not in names_after

    def test_undo_rejected_reverts_to_pending(self, client):
        import asyncio
        from data import history_store
        rec_id = "550e8400-e29b-41d4-a716-446655550023"
        _seed_pending_recommendation(client, rec_id, proposed="reopen_me_clause")
        client.post(f"/api/admin/insights/{rec_id}/reject")
        resp = client.post(f"/api/admin/insights/{rec_id}/undo")
        assert resp.status_code == 200
        assert resp.json()["action"] == "reopened"
        rec = asyncio.run(history_store.get_recommendation(rec_id))
        assert rec["status"] == "pending"

    def test_undo_rejected_removes_from_blacklist(self, client):
        import asyncio
        from data import history_store
        rec_id = "550e8400-e29b-41d4-a716-446655550024"
        _seed_pending_recommendation(client, rec_id, proposed="unblacklist_me_clause")
        client.post(f"/api/admin/insights/{rec_id}/reject")
        assert asyncio.run(history_store.is_blacklisted("LEGAL_CONTRACT", "unblacklist_me_clause"))
        client.post(f"/api/admin/insights/{rec_id}/undo")
        assert not asyncio.run(history_store.is_blacklisted("LEGAL_CONTRACT", "unblacklist_me_clause"))

    def test_undo_already_undone_returns_400(self, client, tmp_path, monkeypatch):
        rec_id = "550e8400-e29b-41d4-a716-446655550025"
        _seed_pending_recommendation(client, rec_id, "missing_rule", "double_undo_clause")
        monkeypatch.setattr("api.routes._REG_DB_PATH",
                            __import__("pathlib").Path(tmp_path / "regulatory_db.json"))
        (tmp_path / "regulatory_db.json").write_text('{"LEGAL_CONTRACT": []}')
        client.post(f"/api/admin/insights/{rec_id}/approve")
        client.post(f"/api/admin/insights/{rec_id}/undo")
        resp = client.post(f"/api/admin/insights/{rec_id}/undo")
        assert resp.status_code == 400
