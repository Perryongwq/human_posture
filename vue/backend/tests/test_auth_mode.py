# backend/tests/test_auth_mode.py
"""Tests for AUTH_MODE migration — AUTH-01, AUTH-02, AUTH-03."""
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user
from app.core.models import JWTClaims


class TestAuthMode:
    """AUTH-01, AUTH-02, AUTH-03: AUTH_MODE=0 bypasses auth, AUTH_MODE=1 requires JWT."""

    def test_auth_mode_0_returns_mock_claims(self):
        """
        AUTH-02: When AUTH_MODE=0, /api/me returns mock claims without JWT.

        Uses FastAPI dependency_overrides (idiomatic pattern) instead of
        settings patching, which doesn't work due to module caching.
        """
        # Simulate AUTH_MODE=0 by overriding the dependency to return mock claims
        mock_dev_claims = JWTClaims(username="dev", payroll="DEV001", deptcode="IT")
        app.dependency_overrides[get_current_user] = lambda: mock_dev_claims

        try:
            with TestClient(app) as client:
                response = client.get("/api/me")
                assert response.status_code == 200
                data = response.json()
                # AUTH-02: Mock claims have specific values
                assert data["username"] == "dev"
                assert data["payroll"] == "DEV001"
                assert data["deptcode"] == "IT"
        finally:
            app.dependency_overrides.clear()

    def test_auth_mode_1_requires_jwt(self):
        """AUTH-03: When AUTH_MODE=1 (default), /api/me requires JWT."""
        # Ensure no overrides — tests real auth behavior
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            response = client.get("/api/me")
            assert response.status_code == 401
