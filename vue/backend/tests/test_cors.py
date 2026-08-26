# backend/tests/test_cors.py
"""Tests for CORS middleware — BE-05."""
from fastapi.testclient import TestClient

from app.main import app


class TestCorsMiddleware:
    """BE-05: CORS preflight and headers."""

    def test_cors_preflight_from_allowed_origin(self):
        """OPTIONS request from allowed origin receives CORS headers."""
        with TestClient(app) as client:
            response = client.options(
                "/api/me",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization",
                }
            )
            assert response.status_code == 200
            assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
            assert "Authorization" in response.headers.get("Access-Control-Allow-Headers", "")

    def test_cors_header_on_actual_request(self):
        """Actual request from allowed origin receives CORS headers."""
        with TestClient(app) as client:
            response = client.get(
                "/health",
                headers={"Origin": "http://localhost:5173"}
            )
            assert response.status_code == 200
            assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
