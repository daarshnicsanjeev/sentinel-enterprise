"""
TDD tests for Phase 8D1 — JWT Authentication.

POST /api/auth/token   → accepts {username, password}, returns {access_token, token_type}
All /api/* write endpoints require Authorization: Bearer <token>

Run: pytest tests/unit/test_auth.py -v
"""
import pytest



# ---------------------------------------------------------------------------
# 1. Token endpoint
# ---------------------------------------------------------------------------

class TestTokenEndpoint:
    def test_login_returns_200(self, client):
        resp = client.post("/api/auth/token", json={"username": "admin", "password": "sentinel123"})
        assert resp.status_code == 200

    def test_login_returns_access_token(self, client):
        resp = client.post("/api/auth/token", json={"username": "admin", "password": "sentinel123"})
        data = resp.json()
        assert "access_token" in data

    def test_login_returns_token_type_bearer(self, client):
        resp = client.post("/api/auth/token", json={"username": "admin", "password": "sentinel123"})
        assert resp.json()["token_type"] == "bearer"

    def test_login_with_analyst_user(self, client):
        resp = client.post("/api/auth/token", json={"username": "analyst", "password": "analyst123"})
        assert resp.status_code == 200

    def test_login_wrong_password_returns_401(self, client):
        resp = client.post("/api/auth/token", json={"username": "admin", "password": "wrongpassword"})
        assert resp.status_code == 401

    def test_login_unknown_user_returns_401(self, client):
        resp = client.post("/api/auth/token", json={"username": "ghost", "password": "anything"})
        assert resp.status_code == 401

    def test_login_missing_fields_returns_422(self, client):
        resp = client.post("/api/auth/token", json={"username": "admin"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 2. Token is a valid JWT
# ---------------------------------------------------------------------------

class TestTokenIsJWT:
    def test_token_has_three_parts(self, client):
        resp = client.post("/api/auth/token", json={"username": "admin", "password": "sentinel123"})
        token = resp.json()["access_token"]
        assert len(token.split(".")) == 3

    def test_token_decodes_without_error(self, client):
        from api.auth import decode_token
        resp = client.post("/api/auth/token", json={"username": "admin", "password": "sentinel123"})
        token = resp.json()["access_token"]
        payload = decode_token(token)
        assert payload is not None

    def test_token_payload_contains_username(self, client):
        from api.auth import decode_token
        resp = client.post("/api/auth/token", json={"username": "admin", "password": "sentinel123"})
        token = resp.json()["access_token"]
        payload = decode_token(token)
        assert payload["sub"] == "admin"

    def test_token_payload_contains_role(self, client):
        from api.auth import decode_token
        resp = client.post("/api/auth/token", json={"username": "admin", "password": "sentinel123"})
        token = resp.json()["access_token"]
        payload = decode_token(token)
        assert "role" in payload

    def test_admin_token_has_admin_role(self, client):
        from api.auth import decode_token
        resp = client.post("/api/auth/token", json={"username": "admin", "password": "sentinel123"})
        token = resp.json()["access_token"]
        payload = decode_token(token)
        assert payload["role"] == "admin"

    def test_analyst_token_has_analyst_role(self, client):
        from api.auth import decode_token
        resp = client.post("/api/auth/token", json={"username": "analyst", "password": "analyst123"})
        token = resp.json()["access_token"]
        payload = decode_token(token)
        assert payload["role"] == "analyst"


# ---------------------------------------------------------------------------
# 3. Protected read endpoint (GET /api/history) still open — read is public
# ---------------------------------------------------------------------------

class TestPublicReadEndpoints:
    def test_history_without_token_returns_200(self, client):
        resp = client.get("/api/history")
        assert resp.status_code == 200

    def test_clauses_without_token_returns_200(self, client):
        resp = client.get("/api/clauses/default")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. Protected write endpoints require token
# ---------------------------------------------------------------------------

class TestProtectedEndpoints:
    def test_override_without_token_returns_401(self, client):
        resp = client.post(
            "/api/override/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            json={"decision": "APPROVED"}
        )
        assert resp.status_code == 401

    def test_override_with_valid_token_does_not_return_401(self, client):
        token_resp = client.post("/api/auth/token", json={"username": "admin", "password": "sentinel123"})
        token = token_resp.json()["access_token"]
        resp = client.post(
            "/api/override/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            json={"decision": "APPROVED"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code != 401

    def test_export_without_token_returns_401(self, client):
        resp = client.get("/api/history/export")
        assert resp.status_code == 401

    def test_export_with_valid_token_does_not_return_401(self, client):
        token_resp = client.post("/api/auth/token", json={"username": "admin", "password": "sentinel123"})
        token = token_resp.json()["access_token"]
        resp = client.get("/api/history/export", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code != 401

    def test_invalid_token_returns_401(self, client):
        resp = client.get(
            "/api/history/export",
            headers={"Authorization": "Bearer this.is.garbage"}
        )
        assert resp.status_code == 401

    def test_post_clauses_without_token_returns_401(self, client):
        resp = client.post("/api/clauses/mytenant", json={"LEGAL_CONTRACT": [{"name": "x", "risk_level": "HIGH"}]})
        assert resp.status_code == 401
