"""Tests for auth.py and the auth-gated HTTP routes.

Unlike test_api.py, these don't need a real database: token
creation/verification is pure functions, and requests that get
rejected for bad auth never reach the database layer. A test
SECRET_KEY / OPERATOR_PASSWORD are set here (via setdefault, so a
real CI-provided value always wins) purely so these tests are
self-contained.
"""

import os
import sys
import time

os.environ.setdefault("SECRET_KEY", "pytest-only-secret-do-not-use-in-prod")
os.environ.setdefault("OPERATOR_PASSWORD", "pytest-only-password")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import auth


class TestTokens:
    def test_valid_token_verifies(self):
        token = auth.create_token()
        assert auth.verify_token(token) is True

    def test_tampered_payload_rejected(self):
        token = auth.create_token()
        payload_b64, sig = token.split(".", 1)
        # Flip the payload but keep the original signature.
        tampered = payload_b64[:-1] + ("A" if payload_b64[-1] != "A" else "B")
        assert auth.verify_token(f"{tampered}.{sig}") is False

    def test_tampered_signature_rejected(self):
        token = auth.create_token()
        payload_b64, sig = token.split(".", 1)
        bad_sig = sig[:-1] + ("A" if sig[-1] != "A" else "B")
        assert auth.verify_token(f"{payload_b64}.{bad_sig}") is False

    def test_garbage_token_rejected(self):
        assert auth.verify_token("not-a-real-token") is False
        assert auth.verify_token("") is False

    def test_expired_token_rejected(self, monkeypatch):
        monkeypatch.setattr(auth, "TOKEN_TTL_SECONDS", -1)
        expired = auth.create_token()
        assert auth.verify_token(expired) is False

    def test_tokens_are_process_stable_across_time(self):
        # Same secret -> a token minted a moment ago is still valid now.
        token = auth.create_token()
        time.sleep(0.1)
        assert auth.verify_token(token) is True


class TestPassword:
    def test_correct_password_accepted(self):
        assert auth.check_password("pytest-only-password") is True

    def test_wrong_password_rejected(self):
        assert auth.check_password("definitely-wrong") is False

    def test_empty_password_rejected(self):
        assert auth.check_password("") is False


class TestProtectedRoutes:
    """HTTP-layer checks via FastAPI's TestClient - these exercise
    request validation and auth wiring, not just the underlying
    Python functions."""

    @classmethod
    def setup_class(cls):
        from fastapi.testclient import TestClient
        from main import app

        cls.client = TestClient(app)

    def test_park_without_token_is_401(self):
        res = self.client.post(
            "/api/park", json={"vehicle_number": "WB-01-AB-1234", "vehicle_type": "car"}
        )
        assert res.status_code == 401

    def test_checkout_without_token_is_401(self):
        res = self.client.post("/api/checkout/WB-01-AB-1234")
        assert res.status_code == 401

    def test_login_wrong_password_is_401(self):
        res = self.client.post("/api/login", json={"password": "nope"})
        assert res.status_code == 401

    def test_login_correct_password_returns_token(self):
        res = self.client.post("/api/login", json={"password": "pytest-only-password"})
        assert res.status_code == 200
        assert "token" in res.json()

    def test_park_rejects_html_in_vehicle_number(self):
        # Regression test for the stored-XSS fix: this must never reach
        # the database - it should fail Pydantic validation (422).
        token = self.client.post(
            "/api/login", json={"password": "pytest-only-password"}
        ).json()["token"]
        res = self.client.post(
            "/api/park",
            json={"vehicle_number": "<img src=x onerror=alert(1)>", "vehicle_type": "car"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422

    def test_park_rejects_bad_vehicle_type(self):
        token = self.client.post(
            "/api/login", json={"password": "pytest-only-password"}
        ).json()["token"]
        res = self.client.post(
            "/api/park",
            json={"vehicle_number": "WB-01-AB-1234", "vehicle_type": "spaceship"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422
