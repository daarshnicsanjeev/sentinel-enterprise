"""
TDD tests for Phase 8C1 — Custom Clause Library API.

GET  /api/clauses/{tenant_id}          → list of clause dicts for that tenant
POST /api/clauses/{tenant_id}          → write new clause list (admin use)
GET  /api/clauses/{tenant_id}/{doc_type} → clauses for a specific doc type

Run: pytest tests/unit/test_custom_clauses.py -v
"""
import json
import pytest



SAMPLE_CLAUSES = {
    "LEGAL_CONTRACT": [
        {"name": "force majeure clause",    "risk_level": "HIGH"},
        {"name": "limitation of liability", "risk_level": "HIGH"},
    ]
}


# ---------------------------------------------------------------------------
# GET /api/clauses/{tenant_id}
# ---------------------------------------------------------------------------

class TestGetClauses:
    def test_get_default_tenant_returns_200(self, client):
        resp = client.get("/api/clauses/default")
        assert resp.status_code == 200

    def test_get_default_returns_dict(self, client):
        resp = client.get("/api/clauses/default")
        assert isinstance(resp.json(), dict)

    def test_get_default_contains_credit_agreement(self, client):
        resp = client.get("/api/clauses/default")
        data = resp.json()
        assert "CREDIT_AGREEMENT" in data

    def test_get_eu_tenant_returns_200(self, client):
        resp = client.get("/api/clauses/EU")
        assert resp.status_code == 200

    def test_get_unknown_tenant_returns_404(self, client):
        resp = client.get("/api/clauses/NONEXISTENT_TENANT_XYZ")
        assert resp.status_code == 404

    def test_get_clause_entries_are_dicts_with_name_and_risk_level(self, client):
        resp = client.get("/api/clauses/default")
        data = resp.json()
        for doc_type, clauses in data.items():
            for clause in clauses:
                assert "name" in clause
                assert "risk_level" in clause


# ---------------------------------------------------------------------------
# GET /api/clauses/{tenant_id}/{doc_type}
# ---------------------------------------------------------------------------

class TestGetClausesByDocType:
    def test_get_specific_doc_type_returns_list(self, client):
        resp = client.get("/api/clauses/default/CREDIT_AGREEMENT")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_specific_doc_type_has_clauses(self, client):
        resp = client.get("/api/clauses/default/CREDIT_AGREEMENT")
        assert len(resp.json()) > 0

    def test_get_unknown_doc_type_returns_empty_list(self, client):
        resp = client.get("/api/clauses/default/INVOICE_TYPE_UNKNOWN")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_unknown_tenant_doc_type_returns_404(self, client):
        resp = client.get("/api/clauses/GHOST_TENANT/CREDIT_AGREEMENT")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/clauses/{tenant_id}
# ---------------------------------------------------------------------------

class TestPostClauses:
    def test_post_creates_custom_tenant(self, client, admin_headers, tmp_path, monkeypatch):
        import api.routes as routes_mod
        monkeypatch.setattr(routes_mod, "_CUSTOM_CLAUSES_DIR", tmp_path)
        resp = client.post(
            "/api/clauses/mytenant",
            json=SAMPLE_CLAUSES,
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)

    def test_post_then_get_returns_written_clauses(self, client, admin_headers, tmp_path, monkeypatch):
        import api.routes as routes_mod
        monkeypatch.setattr(routes_mod, "_CUSTOM_CLAUSES_DIR", tmp_path)
        client.post("/api/clauses/mytenant", json=SAMPLE_CLAUSES, headers=admin_headers)
        resp = client.get("/api/clauses/mytenant")
        assert resp.status_code == 200
        data = resp.json()
        assert "LEGAL_CONTRACT" in data
        names = [c["name"] for c in data["LEGAL_CONTRACT"]]
        assert "force majeure clause" in names

    def test_post_rejects_invalid_risk_level(self, client, admin_headers, tmp_path, monkeypatch):
        import api.routes as routes_mod
        monkeypatch.setattr(routes_mod, "_CUSTOM_CLAUSES_DIR", tmp_path)
        bad_clauses = {
            "LEGAL_CONTRACT": [{"name": "some clause", "risk_level": "CRITICAL"}]
        }
        resp = client.post("/api/clauses/badtenant", json=bad_clauses, headers=admin_headers)
        assert resp.status_code == 422

    def test_post_rejects_missing_name_field(self, client, admin_headers, tmp_path, monkeypatch):
        import api.routes as routes_mod
        monkeypatch.setattr(routes_mod, "_CUSTOM_CLAUSES_DIR", tmp_path)
        bad_clauses = {
            "LEGAL_CONTRACT": [{"risk_level": "HIGH"}]
        }
        resp = client.post("/api/clauses/badtenant", json=bad_clauses, headers=admin_headers)
        assert resp.status_code == 422

    def test_post_rejects_invalid_tenant_id(self, client, admin_headers):
        # Path traversal attempt: server either rejects via validation (400/422)
        # or routing resolves the path away (404) — all are safe rejections.
        resp = client.post("/api/clauses/../../etc", json=SAMPLE_CLAUSES, headers=admin_headers)
        assert resp.status_code in (400, 404, 422)
