"""
TDD tests for Phase 8D2 — Role-Based Access Control.

Roles:
  analyst — can read history, analyze documents, submit feedback
  admin   — everything analyst can do, plus: override, export, post clauses

Run: pytest tests/unit/test_rbac.py -v
"""
import pytest



@pytest.fixture
def admin_token(client):
    resp = client.post("/api/auth/token", json={"username": "admin", "password": "sentinel123"})
    return resp.json()["access_token"]


@pytest.fixture
def analyst_token(client):
    resp = client.post("/api/auth/token", json={"username": "analyst", "password": "analyst123"})
    return resp.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def analyst_headers(analyst_token):
    return {"Authorization": f"Bearer {analyst_token}"}


# ---------------------------------------------------------------------------
# Admin role — can access all protected endpoints
# ---------------------------------------------------------------------------

class TestAdminCanAccessAll:
    def test_admin_can_export(self, client, admin_headers):
        resp = client.get("/api/history/export", headers=admin_headers)
        assert resp.status_code == 200

    def test_admin_can_post_clauses(self, client, admin_headers, tmp_path, monkeypatch):
        import api.routes as routes_mod
        monkeypatch.setattr(routes_mod, "_CUSTOM_CLAUSES_DIR", tmp_path)
        resp = client.post(
            "/api/clauses/rbac_tenant",
            json={"LEGAL_CONTRACT": [{"name": "governing law", "risk_level": "HIGH"}]},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)

    def test_admin_can_override(self, client, admin_headers):
        # No pending trace, so 404 — but NOT 401/403
        resp = client.post(
            "/api/override/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            json={"decision": "APPROVED"},
            headers=admin_headers,
        )
        assert resp.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# Analyst role — blocked from admin-only endpoints
# ---------------------------------------------------------------------------

class TestAnalystBlocked:
    def test_analyst_cannot_export(self, client, analyst_headers):
        resp = client.get("/api/history/export", headers=analyst_headers)
        assert resp.status_code == 403

    def test_analyst_cannot_post_clauses(self, client, analyst_headers):
        resp = client.post(
            "/api/clauses/rbac_tenant",
            json={"LEGAL_CONTRACT": [{"name": "x", "risk_level": "HIGH"}]},
            headers=analyst_headers,
        )
        assert resp.status_code == 403

    def test_analyst_cannot_override(self, client, analyst_headers):
        resp = client.post(
            "/api/override/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            json={"decision": "APPROVED"},
            headers=analyst_headers,
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Analyst role — allowed on read endpoints
# ---------------------------------------------------------------------------

class TestAnalystCanRead:
    def test_analyst_can_get_history(self, client, analyst_headers):
        resp = client.get("/api/history", headers=analyst_headers)
        assert resp.status_code == 200

    def test_analyst_can_get_clauses(self, client, analyst_headers):
        resp = client.get("/api/clauses/default", headers=analyst_headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# require_role helper
# ---------------------------------------------------------------------------

class TestRequireRoleHelper:
    def test_require_role_admin_raises_403_for_analyst(self):
        from api.auth import require_role
        import pytest
        from fastapi import HTTPException
        analyst_user = {"username": "analyst", "role": "analyst"}
        guard = require_role("admin")
        with pytest.raises(HTTPException) as exc_info:
            guard(analyst_user)
        assert exc_info.value.status_code == 403

    def test_require_role_admin_passes_for_admin(self):
        from api.auth import require_role
        admin_user = {"username": "admin", "role": "admin"}
        guard = require_role("admin")
        result = guard(admin_user)  # should not raise
        assert result == admin_user

    def test_require_role_analyst_passes_for_analyst(self):
        from api.auth import require_role
        analyst_user = {"username": "analyst", "role": "analyst"}
        guard = require_role("analyst")
        result = guard(analyst_user)
        assert result == analyst_user
