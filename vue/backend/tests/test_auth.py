# backend/tests/test_auth.py
"""Tests for auth module — BE-02, BE-03."""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import make_test_app_jwe


class TestAuthDependency:
    """BE-02, BE-03: Auth dependency returns correct responses."""
    
    def test_missing_auth_header_returns_401_not_422(self):
        """BE-02: Missing Authorization header returns 401 (not 422)."""
        with TestClient(app) as client:
            response = client.get("/api/me")
            assert response.status_code == 401
    
    def test_invalid_jwt_returns_401(self):
        """BE-03: Invalid token returns 401."""
        with TestClient(app) as client:
            response = client.get(
                "/api/me",
                headers={"Authorization": "Bearer invalid-token"}
            )
            assert response.status_code == 401
            assert "Invalid token" in response.json()["detail"]
    
    def test_valid_jwt_returns_200_with_claims(self):
        """Valid app JWE returns 200 with claims."""
        token = make_test_app_jwe()
        with TestClient(app) as client:
            response = client.get(
                "/api/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["username"] == "testuser"
