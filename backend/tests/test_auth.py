# ==========================================
# tests/test_auth.py — Auth Endpoint Tests (Neon DB)
# ==========================================
# Tests against the real Neon PostgreSQL database.
# All test emails use the @testdomain.dev domain so the
# autouse cleanup fixture in conftest.py wipes them after each test.
#
# Tests:
#   - Signup: success, duplicate email, weak password, invalid email
#   - Login:  success (returns tokens), wrong password, non-existent email,
#             generic error message (anti-enumeration)
#   - /me:    valid token, no token, invalid token, expired token,
#             refresh token rejected as access token
#   - Refresh: success with token rotation, old token revoked after rotation,
#              invalid token, access token rejected as refresh token
#   - Logout:  revokes refresh token, requires auth
# ==========================================

import pytest
from datetime import timedelta

from fastapi.testclient import TestClient
from app.auth.utils import _create_token, ACCESS_TOKEN_TYPE


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def register_and_login(client, email="test@testdomain.dev", password="securepassword123"):
    """Sign up a user and log them in. Returns the token response dict."""
    client.post("/auth/signup", json={"email": email, "password": password})
    res = client.post("/auth/login", json={"email": email, "password": password})
    return res.json()


# ===========================================================================
# Signup
# ===========================================================================

class TestSignup:
    def test_signup_success(self, client):
        res = client.post("/auth/signup", json={
            "email": "user@testdomain.dev",
            "password": "strongpass99",
        })
        assert res.status_code == 201
        body = res.json()
        assert body["email"] == "user@testdomain.dev"
        assert "id" in body
        assert "created_at" in body
        assert "hashed_password" not in body   # must never be exposed

    def test_signup_duplicate_email(self, client):
        payload = {"email": "dup@testdomain.dev", "password": "somepassword1"}
        client.post("/auth/signup", json=payload)
        res = client.post("/auth/signup", json=payload)
        assert res.status_code == 409
        assert "already exists" in res.json()["detail"]

    def test_signup_weak_password(self, client):
        res = client.post("/auth/signup", json={
            "email": "weak@testdomain.dev",
            "password": "short",   # < 8 chars
        })
        assert res.status_code == 422   # Pydantic validation error

    def test_signup_invalid_email(self, client):
        res = client.post("/auth/signup", json={
            "email": "not-an-email",
            "password": "validpassword123",
        })
        assert res.status_code == 422


# ===========================================================================
# Login
# ===========================================================================

class TestLogin:
    def test_login_success(self, client):
        client.post("/auth/signup", json={"email": "login@testdomain.dev", "password": "mypassword123"})
        res = client.post("/auth/login", json={"email": "login@testdomain.dev", "password": "mypassword123"})
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0

    def test_login_wrong_password(self, client):
        client.post("/auth/signup", json={"email": "user2@testdomain.dev", "password": "correctpass1"})
        res = client.post("/auth/login", json={"email": "user2@testdomain.dev", "password": "wrongpass99"})
        assert res.status_code == 401

    def test_login_nonexistent_email(self, client):
        res = client.post("/auth/login", json={"email": "ghost@testdomain.dev", "password": "somepassword"})
        assert res.status_code == 401

    def test_login_error_messages_are_generic(self, client):
        """Both wrong-password and no-such-email return the same detail to prevent email enumeration."""
        client.post("/auth/signup", json={"email": "real@testdomain.dev", "password": "realpassword1"})
        res_wrong_pw = client.post("/auth/login", json={"email": "real@testdomain.dev", "password": "wrongpass"})
        res_no_user  = client.post("/auth/login", json={"email": "fake@testdomain.dev", "password": "wrongpass"})
        assert res_wrong_pw.json()["detail"] == res_no_user.json()["detail"]


# ===========================================================================
# /auth/me
# ===========================================================================

class TestMe:
    def test_me_authenticated(self, client):
        tokens = register_and_login(client)
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        assert res.status_code == 200
        assert res.json()["email"] == "test@testdomain.dev"

    def test_me_no_token(self, client):
        res = client.get("/auth/me")
        assert res.status_code == 401

    def test_me_invalid_token(self, client):
        res = client.get("/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
        assert res.status_code == 401

    def test_me_expired_token(self, client):
        """An access token with a negative expiry must be rejected."""
        register_and_login(client)   # creates the user in Neon
        expired_token = _create_token(
            data={"sub": "1"},
            token_type=ACCESS_TOKEN_TYPE,
            expires_delta=timedelta(seconds=-1),
        )
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert res.status_code == 401

    def test_me_refresh_token_rejected(self, client):
        """A refresh token must NOT work as an access token."""
        tokens = register_and_login(client)
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
        assert res.status_code == 401


# ===========================================================================
# Token refresh
# ===========================================================================

class TestRefresh:
    def test_refresh_success(self, client):
        tokens = register_and_login(client)
        res = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert res.status_code == 200
        new_tokens = res.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        # New tokens must be different (rotation)
        assert new_tokens["access_token"]  != tokens["access_token"]
        assert new_tokens["refresh_token"] != tokens["refresh_token"]

    def test_refresh_old_token_revoked_after_rotation(self, client):
        """After a refresh, the old refresh token must not work again."""
        tokens = register_and_login(client)
        client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        res = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert res.status_code == 401

    def test_refresh_invalid_token(self, client):
        res = client.post("/auth/refresh", json={"refresh_token": "not.a.real.token"})
        assert res.status_code == 401

    def test_refresh_with_access_token_rejected(self, client):
        """An access token must NOT work as a refresh token."""
        tokens = register_and_login(client)
        res = client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})
        assert res.status_code == 401


# ===========================================================================
# Logout
# ===========================================================================

class TestLogout:
    def test_logout_success(self, client):
        tokens = register_and_login(client)
        res = client.post(
            "/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert res.status_code == 204

    def test_logout_revokes_refresh_token(self, client):
        """After logout, the refresh token must be rejected."""
        tokens = register_and_login(client)
        client.post(
            "/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        res = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert res.status_code == 401

    def test_logout_requires_auth(self, client):
        """Logout without a valid access token must be rejected."""
        tokens = register_and_login(client)
        res = client.post(
            "/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            # No Authorization header
        )
        assert res.status_code == 401
