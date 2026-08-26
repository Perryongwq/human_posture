# backend/tests/conftest.py
"""Shared pytest fixtures for backend tests."""
import base64
import json
import os
import time
from typing import Generator

# ═══════════════════════════════════════════════════════════════════
# CRITICAL: Set env vars BEFORE any app imports to avoid ValidationError
# pydantic-settings caches settings at module load time
# ═══════════════════════════════════════════════════════════════════
_TEST_APP_JWE_KEY_BYTES = b'\x01' * 32
_TEST_APP_JWE_KEY_B64 = base64.urlsafe_b64encode(_TEST_APP_JWE_KEY_BYTES).rstrip(b"=").decode()
os.environ["JWT_JWE_KEY"] = _TEST_APP_JWE_KEY_B64

from jwcrypto import jwe, jwk
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user
from app.core.models import JWTClaims


# Test app JWE key — canonical value used everywhere
TEST_APP_JWE_KEY_B64 = _TEST_APP_JWE_KEY_B64


def make_test_app_jwe(
    username: str = "testuser",
    payroll: str = "T001",
    deptcode: str = "IT",
    expired: bool = False,
) -> str:
    """Generate a test app JWE token (dir/A256GCM) using the test key."""
    now = int(time.time())
    payload = {
        "username": username,
        "payroll": payroll,
        "deptcode": deptcode,
        "exp": now - 3600 if expired else now + 3600,
    }
    k_val = base64.urlsafe_b64encode(_TEST_APP_JWE_KEY_BYTES).rstrip(b"=").decode()
    key = jwk.JWK(kty="oct", k=k_val)
    token = jwe.JWE(
        json.dumps(payload).encode(),
        protected=json.dumps({"alg": "dir", "enc": "A256GCM"}),
    )
    token.add_recipient(key)
    return token.serialize(compact=True)


@pytest.fixture
def test_settings(monkeypatch):
    """Override settings for testing."""
    monkeypatch.setenv("JWT_JWE_KEY", TEST_APP_JWE_KEY_B64)
    monkeypatch.setenv("AUTH_MODE", "1")


@pytest.fixture
def mock_user() -> JWTClaims:
    """Mock user claims for auth-bypassed tests."""
    return JWTClaims(username="testuser", payroll="T001", deptcode="TEST")


@pytest.fixture
def client(mock_user: JWTClaims) -> Generator[TestClient, None, None]:
    """TestClient with auth bypassed — returns known mock claims."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client() -> Generator[TestClient, None, None]:
    """TestClient with no auth override — tests real 401 behaviour."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def valid_app_jwe() -> str:
    """A valid app JWE token for testing."""
    return make_test_app_jwe()


@pytest.fixture
def expired_app_jwe() -> str:
    """An expired app JWE token for testing."""
    return make_test_app_jwe(expired=True)
