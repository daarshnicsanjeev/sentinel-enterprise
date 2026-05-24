"""
Unit tests for data/history_store.py — cache sanitization and score clamping.
"""
import pytest


class TestClampScore:
    def test_normal_value_unchanged(self):
        from data.history_store import _clamp_score
        assert _clamp_score(0.75) == 0.75

    def test_clamps_above_one(self):
        from data.history_store import _clamp_score
        assert _clamp_score(1.5) == 1.0

    def test_clamps_below_zero(self):
        from data.history_store import _clamp_score
        assert _clamp_score(-0.5) == 0.0

    def test_zero_and_one_boundary(self):
        from data.history_store import _clamp_score
        assert _clamp_score(0.0) == 0.0
        assert _clamp_score(1.0) == 1.0

    def test_non_numeric_string_returns_zero(self):
        from data.history_store import _clamp_score
        assert _clamp_score("abc") == 0.0

    def test_none_returns_zero(self):
        from data.history_store import _clamp_score
        assert _clamp_score(None) == 0.0

    def test_list_returns_zero(self):
        from data.history_store import _clamp_score
        assert _clamp_score([0.5]) == 0.0

    def test_large_positive_clamped(self):
        from data.history_store import _clamp_score
        assert _clamp_score(999999) == 1.0

    def test_nan_returns_zero(self):
        from data.history_store import _clamp_score
        assert _clamp_score(float("nan")) == 0.0


class TestSanitizeCachePayload:
    def _call(self, payload: dict) -> dict:
        from data.history_store import _sanitize_cache_payload
        return _sanitize_cache_payload(payload)

    def test_valid_decision_preserved(self):
        result = self._call({"final_decision": "APPROVED"})
        assert result["final_decision"] == "APPROVED"

    def test_invalid_decision_becomes_unknown(self):
        result = self._call({"final_decision": "INJECT\nfake"})
        assert result["final_decision"] == "UNKNOWN"

    def test_missing_decision_becomes_unknown(self):
        result = self._call({})
        assert result["final_decision"] == "UNKNOWN"

    def test_valid_risk_preserved(self):
        result = self._call({"hallucination_risk": "high"})
        assert result["hallucination_risk"] == "high"

    def test_invalid_risk_becomes_medium(self):
        result = self._call({"hallucination_risk": "extreme"})
        assert result["hallucination_risk"] == "medium"

    def test_score_clamped_above_one(self):
        result = self._call({"evaluation_score": 999.0})
        assert result["evaluation_score"] == 1.0

    def test_confidence_clamped_below_zero(self):
        result = self._call({"routing_confidence": -5.0})
        assert result["routing_confidence"] == 0.0

    def test_doc_type_truncated_at_100_chars(self):
        result = self._call({"doc_type": "X" * 200})
        assert len(result["doc_type"]) == 100

    def test_trace_id_truncated_at_36_chars(self):
        result = self._call({"trace_id": "a" * 100})
        assert len(result["trace_id"]) == 36

    def test_clause_results_sanitized(self):
        payload = {
            "clause_results": [
                {"clause": "C" * 300, "status": "PRESENT", "evidence": "E" * 500},
                {"clause": "missing clause", "status": "MISSING", "evidence": ""},
            ]
        }
        result = self._call(payload)
        assert len(result["clause_results"][0]["clause"]) == 200
        assert len(result["clause_results"][0]["evidence"]) == 300
        assert result["clause_results"][0]["status"] == "PRESENT"
        assert result["clause_results"][1]["status"] == "MISSING"

    def test_invalid_clause_status_becomes_missing(self):
        payload = {"clause_results": [{"clause": "test", "status": "INJECT", "evidence": ""}]}
        result = self._call(payload)
        assert result["clause_results"][0]["status"] == "MISSING"

    def test_type_field_always_done(self):
        result = self._call({"type": "evil"})
        assert result["type"] == "done"

    def test_non_dict_clause_entries_skipped(self):
        payload = {"clause_results": ["not a dict", 42, None]}
        result = self._call(payload)
        assert result["clause_results"] == []

    def test_clause_results_history_always_empty(self):
        payload = {"clause_results_history": [{"old": "data"}]}
        result = self._call(payload)
        assert result["clause_results_history"] == []
