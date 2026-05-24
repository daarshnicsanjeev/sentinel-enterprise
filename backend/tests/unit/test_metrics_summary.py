"""
Unit + integration tests for GET /api/metrics/summary (Phase 9B).
TDD: RED first — all tests fail until endpoint is implemented.
Run: pytest tests/unit/test_metrics_summary.py -v
"""
import pytest




class TestMetricsSummaryEndpoint:
    def test_metrics_summary_returns_200(self, client):
        resp = client.get("/api/metrics/summary")
        assert resp.status_code == 200

    def test_metrics_summary_returns_json(self, client):
        resp = client.get("/api/metrics/summary")
        data = resp.json()
        assert isinstance(data, dict)

    def test_metrics_includes_total_field(self, client):
        resp = client.get("/api/metrics/summary")
        data = resp.json()
        assert "total" in data
        assert isinstance(data["total"], int)

    def test_metrics_includes_by_decision(self, client):
        resp = client.get("/api/metrics/summary")
        data = resp.json()
        assert "by_decision" in data
        assert isinstance(data["by_decision"], dict)

    def test_metrics_avg_faithfulness_is_float_between_0_and_1(self, client):
        resp = client.get("/api/metrics/summary")
        data = resp.json()
        assert "avg_faithfulness" in data
        f = data["avg_faithfulness"]
        assert isinstance(f, (int, float))
        assert 0.0 <= f <= 1.0

    def test_metrics_includes_risk_distribution(self, client):
        resp = client.get("/api/metrics/summary")
        data = resp.json()
        assert "risk_distribution" in data
        rd = data["risk_distribution"]
        assert isinstance(rd, dict)
        assert "low" in rd
        assert "medium" in rd
        assert "high" in rd

    def test_metrics_daily_last_7_days_is_dict(self, client):
        resp = client.get("/api/metrics/summary")
        data = resp.json()
        assert "daily_last_7_days" in data
        assert isinstance(data["daily_last_7_days"], dict)

    def test_metrics_returns_zeros_when_no_history(self, client):
        """With empty (or test) DB the total is an integer and avg_faithfulness defaults to 0."""
        resp = client.get("/api/metrics/summary")
        data = resp.json()
        assert isinstance(data["total"], int)
        assert isinstance(data["avg_faithfulness"], (int, float))

    def test_metrics_risk_counts_are_non_negative_ints(self, client):
        resp = client.get("/api/metrics/summary")
        rd = resp.json()["risk_distribution"]
        for key in ("low", "medium", "high"):
            assert isinstance(rd[key], int)
            assert rd[key] >= 0

    def test_metrics_by_decision_values_are_non_negative_ints(self, client):
        resp = client.get("/api/metrics/summary")
        by_dec = resp.json()["by_decision"]
        for v in by_dec.values():
            assert isinstance(v, int)
            assert v >= 0
