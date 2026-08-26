# backend/tests/test_routes.py
"""Tests for route handlers — BE-01, BE-07."""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import make_test_app_jwe


class TestHealthEndpoint:
    """Health check is unauthenticated."""

    def test_health_returns_ok(self):
        """GET /health returns 200 with status ok."""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}


class TestApiMeEndpoint:
    """BE-07: /api/me returns JWE claims for authenticated user."""

    def test_api_me_with_valid_jwt_returns_claims(self):
        """GET /api/me with valid app JWE returns claims."""
        token = make_test_app_jwe()
        with TestClient(app) as client:
            response = client.get(
                "/api/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["username"] == "testuser"
            assert data["payroll"] == "T001"
            assert data["deptcode"] == "IT"

    def test_api_me_without_auth_returns_401(self):
        """BE-01: GET /api/me without Authorization header returns 401 (not 422)."""
        with TestClient(app) as client:
            response = client.get("/api/me")
            assert response.status_code == 401
            assert "Not authenticated" in response.json()["detail"]

    def test_api_me_with_expired_jwt_returns_401(self):
        """GET /api/me with expired app JWE returns 401."""
        token = make_test_app_jwe(expired=True)
        with TestClient(app) as client:
            response = client.get(
                "/api/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 401
            assert "expired" in response.json()["detail"].lower()

    def test_api_me_with_invalid_jwt_returns_401(self):
        """GET /api/me with invalid token returns 401."""
        with TestClient(app) as client:
            response = client.get(
                "/api/me",
                headers={"Authorization": "Bearer invalid-token"}
            )
            assert response.status_code == 401
            assert "Invalid token" in response.json()["detail"]
