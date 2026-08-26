# backend/tests/test_rbac_integration.py
"""
Integration tests for /api/whoami with RBAC wired.

Exercises the full HTTP stack (TestClient) for the whoami route across
AUTH_MODE=0/1/2 scenarios including access granted, denied (level, dept,
user not found), and RBAC unavailable.
"""
import json
import os
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

# Ensure JWT_JWE_KEY is set before any app imports
from tests.conftest import make_test_app_jwe, TEST_APP_JWE_KEY_B64

from app.main import app
from app.core.auth import get_current_user
from app.core.models import JWTClaims
from app.core.rbac import _parse_csv_response

# ── Test data ─────────────────────────────────────────────────────────────────

# These constants mirror the ones in test_rbac.py for consistency.
SAMPLE_USERRIGHT_CSV = (
    "cdc0145,rid0010,rid0011,rto0006,rto0017,rid0012,noc0008,idn0001\n"
    "MES06675,,SP5121,GR_EWOS_INSTRUCTION,,11,0142,\n"
    "ABC12345,,SP5143,GR_EWOS_INSTRUCTION,,20,0142,\n"
)

SAMPLE_SCREENRIGHT_CSV = (
    'rto0006,idn0001,rto0017,rto0018,rid0014,msc14036,noc0008\n'
    'GR_EWOS_INSTRUCTION,100001,INSTRUCTION_ENTRY_SCREEN,Instruction Entry Screen,20,"SP5143,SP5153,SP5123,SP5121",0142\n'
    'GR_EWOS_INSTRUCTION,100003,LOT_INSTRUCTION_REGISTER_SCREEN,Lot Instruction Register Screen,10,"SP5143,SP5153,SP5123,SP5121,SP5122,SP5131,MMP614,MMC6F3,SP5112,FM2668",0142\n'
)

PARSED_USERRIGHT = _parse_csv_response(SAMPLE_USERRIGHT_CSV)
PARSED_SCREENRIGHT = _parse_csv_response(SAMPLE_SCREENRIGHT_CSV)

# ── Integration screenright data ───────────────────────────────────────────────
# require_rbac(settings.APP_SCREEN_ID) is evaluated at import time — the closure
# captures whatever APP_SCREEN_ID was in settings when example.py was first imported.
# We read the actual captured value at test-module import time to build matching screenright rows.
from app.core.config import settings as _app_settings

# The /api/whoami route uses require_rbac("PROTECTED_SCREEN") — match that literal ID.
_CAPTURED_SCREEN_ID = "PROTECTED_SCREEN"

# For access-granted tests: min_level=10, SP5121 in allowed_depts
_SCREEN_GRANT = [
    {"rto0006": "GR_EWOS_INSTRUCTION", "idn0001": "100099",
     "rto0017": _CAPTURED_SCREEN_ID, "rto0018": "Integration Test Screen",
     "rid0014": "10", "msc14036": "SP5143,SP5153,SP5123,SP5121,SP5122",
     "noc0008": "0142"},
]

# For level-denied tests: min_level=20 — MES06675 (level 11) can't pass
_SCREEN_HIGH_LEVEL = [
    {"rto0006": "GR_EWOS_INSTRUCTION", "idn0001": "100099",
     "rto0017": _CAPTURED_SCREEN_ID, "rto0018": "High Level Screen",
     "rid0014": "20", "msc14036": "SP5143,SP5153,SP5123,SP5121",
     "noc0008": "0142"},
]

# For dept-denied tests: NOTDEPT not in allowed_depts
_SCREEN_RESTRICTED_DEPT = [
    {"rto0006": "GR_EWOS_INSTRUCTION", "idn0001": "100099",
     "rto0017": _CAPTURED_SCREEN_ID, "rto0018": "Restricted Dept Screen",
     "rid0014": "10", "msc14036": "SP5143,SP5153,SP5123",
     "noc0008": "0142"},
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mock_settings(auth_mode: int, app_name: str = "test_app"):
    """Build a MagicMock settings object for patching app.rbac.settings."""
    mock_s = MagicMock()
    mock_s.AUTH_MODE = auth_mode
    mock_s.APP_NAME = app_name
    mock_s.RBAC_API_URL = "http://example.com"
    mock_s.RBAC_API_KEY = "test-key"
    mock_s.REDIS_EXPIRE = 10800
    return mock_s


def _redis_mock_with_data(userright=None, screenright=None, app_name: str = "test_app"):
    """Build a mock Redis client whose .get() returns JSON-encoded RBAC data."""
    ur = userright if userright is not None else PARSED_USERRIGHT
    sr = screenright if screenright is not None else _SCREEN_GRANT
    mock_redis = MagicMock()
    mock_redis.get.side_effect = lambda key: {
        f"{app_name}_userright": json.dumps(ur),
        f"{app_name}_screenright": json.dumps(sr),
    }.get(key)
    return mock_redis


# ── Test 1: AUTH_MODE=1 — valid JWT, no RBAC check ───────────────────────────

def test_whoami_auth_mode_1_no_rbac_check():
    """AUTH_MODE=1: /api/whoami with valid JWT returns 200. No Redis interaction."""
    token = make_test_app_jwe(payroll="MES06675", deptcode="SP5121")
    mock_settings = _make_mock_settings(auth_mode=1)

    with patch("app.core.rbac.settings", mock_settings), \
         patch("app.core.rbac.get_redis_read") as mock_redis_read:
        with TestClient(app) as client:
            resp = client.get("/api/whoami", headers={"Authorization": f"Bearer {token}"})
        mock_redis_read.assert_not_called()

    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Hello, testuser!"
    assert data["payroll"] == "MES06675"
    assert data["department"] == "SP5121"


# ── Test 2: AUTH_MODE=0 — mock dev claims, no JWT required ───────────────────

def test_whoami_auth_mode_0_returns_mock_claims():
    """AUTH_MODE=0: /api/whoami without JWT returns 200 with mock dev claims."""
    mock_claims = JWTClaims(username="dev", payroll="DEV001", deptcode="IT")
    mock_settings = _make_mock_settings(auth_mode=0)

    app.dependency_overrides[get_current_user] = lambda: mock_claims
    try:
        with patch("app.core.rbac.settings", mock_settings):
            with TestClient(app) as client:
                resp = client.get("/api/whoami")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["payroll"] == "DEV001"
    assert data["department"] == "IT"  # mock "IT" used directly — no normalization


# ── Test 3: AUTH_MODE=2 — access granted (level OK, dept OK) ─────────────────

def test_whoami_auth_mode_2_access_granted():
    """AUTH_MODE=2: MES06675/SP5121 (pre-normalized JWT) → rbac_level=11 → 200.

    Screenright data uses rto0017="PROTECTED_SCREEN" to match the route's
    require_rbac("PROTECTED_SCREEN") call. min_level=10, SP5121 is in
    allowed_depts → access granted.
    """
    token = make_test_app_jwe(payroll="MES06675", deptcode="SP5121")
    mock_settings = _make_mock_settings(auth_mode=2)
    mock_redis = _redis_mock_with_data(screenright=_SCREEN_GRANT)

    with patch("app.core.rbac.settings", mock_settings), \
         patch("app.core.rbac.get_redis_read", return_value=mock_redis):
        with TestClient(app) as client:
            resp = client.get("/api/whoami", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["payroll"] == "MES06675"
    assert data["department"] == "SP5121"


# ── Test 4: AUTH_MODE=2 — access denied (rbac_level too low) ─────────────────

def test_whoami_auth_mode_2_access_denied_level():
    """AUTH_MODE=2: MES06675/SP5121 (pre-normalized JWT, rbac_level=11) when min_level=20 → 403.

    Uses screenright data with rto0017="PROTECTED_SCREEN" and rid0014=20 (above user's level 11).
    """
    token = make_test_app_jwe(payroll="MES06675", deptcode="SP5121")
    mock_settings = _make_mock_settings(auth_mode=2)
    mock_redis = _redis_mock_with_data(screenright=_SCREEN_HIGH_LEVEL)

    with patch("app.core.rbac.settings", mock_settings), \
         patch("app.core.rbac.get_redis_read", return_value=mock_redis):
        with TestClient(app) as client:
            resp = client.get("/api/whoami", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 403
    assert "Insufficient RBAC level" in resp.json()["detail"]


# ── Test 5: AUTH_MODE=2 — access denied (dept not in allowed_depts) ──────────

def test_whoami_auth_mode_2_access_denied_dept():
    """AUTH_MODE=2: User with JWT dept NOTDEPT (pre-normalized) not in screen's allowed_depts → 403.

    Uses screenright data with rto0017="PROTECTED_SCREEN" and allowed_depts that excludes NOTDEPT.
    User is found in userright (level OK) but dept check fails.
    """
    token = make_test_app_jwe(payroll="MES06675", deptcode="NOTDEPT")
    mock_settings = _make_mock_settings(auth_mode=2)

    # Userright stores "NOTDEPT" — user IS found
    userright_with_notdept = [
        {"cdc0145": "MES06675", "rid0011": "NOTDEPT", "rid0012": "11"},
    ]
    mock_redis = _redis_mock_with_data(
        userright=userright_with_notdept,
        screenright=_SCREEN_RESTRICTED_DEPT,
    )

    with patch("app.core.rbac.settings", mock_settings), \
         patch("app.core.rbac.get_redis_read", return_value=mock_redis):
        with TestClient(app) as client:
            resp = client.get("/api/whoami", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 403
    assert "Department not authorized" in resp.json()["detail"]


# ── Test 6: AUTH_MODE=2 — user not found in userright ────────────────────────

def test_whoami_auth_mode_2_user_not_found():
    """AUTH_MODE=2: JWT payroll=UNKNOWN not in userright → 403 No app access."""
    token = make_test_app_jwe(payroll="UNKNOWN", deptcode="XX")
    mock_settings = _make_mock_settings(auth_mode=2)
    mock_redis = _redis_mock_with_data(screenright=_SCREEN_GRANT)

    with patch("app.core.rbac.settings", mock_settings), \
         patch("app.core.rbac.get_redis_read", return_value=mock_redis):
        with TestClient(app) as client:
            resp = client.get("/api/whoami", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 403
    assert "No app access" in resp.json()["detail"]


# ── Test 7: AUTH_MODE=2 — RBAC unavailable (Redis + API both down) ────────────

def test_whoami_auth_mode_2_rbac_unavailable():
    """AUTH_MODE=2: Redis returns None + API raises ConnectError → 503 RBAC unavailable."""
    token = make_test_app_jwe(payroll="MES06675", deptcode="SP5121")
    mock_settings = _make_mock_settings(auth_mode=2)

    with patch("app.core.rbac.settings", mock_settings), \
         patch("app.core.rbac.get_redis_read", return_value=None), \
         patch("app.core.rbac.get_redis_write", return_value=None), \
         patch("app.core.rbac._fetch_user_right", side_effect=httpx.ConnectError("down")), \
         patch("app.core.rbac._fetch_screen_right", side_effect=httpx.ConnectError("down")):
        with TestClient(app) as client:
            resp = client.get("/api/whoami", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 503
    assert "RBAC unavailable" in resp.json()["detail"]
