# backend/tests/test_rbac.py
"""
Unit tests for backend/app/rbac.py.

Covers:
  - _parse_csv_response: pure CSV parsing
  - check_user_access: pure lookup
  - require_rbac: FastAPI dependency behavior (no-op, Redis hit, Redis miss, 403, 503)
"""
import json
import os

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure JWT_JWE_KEY is set before any app imports
from tests.conftest import TEST_APP_JWE_KEY_B64
os.environ.setdefault("JWT_JWE_KEY", TEST_APP_JWE_KEY_B64)

from app.core.models import JWTClaims
from app.core.rbac import _parse_csv_response, check_user_access, require_rbac

# ── Test data ─────────────────────────────────────────────────────────────────

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

# Pre-parsed versions for Redis mock responses
PARSED_USERRIGHT = _parse_csv_response(SAMPLE_USERRIGHT_CSV)
PARSED_SCREENRIGHT = _parse_csv_response(SAMPLE_SCREENRIGHT_CSV)

# ── _parse_csv_response tests ─────────────────────────────────────────────────

class TestParseCsvResponse:
    def test_userright_csv_returns_list_of_dicts(self):
        result = _parse_csv_response(SAMPLE_USERRIGHT_CSV)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_userright_csv_has_correct_keys(self):
        result = _parse_csv_response(SAMPLE_USERRIGHT_CSV)
        assert result[0]["cdc0145"] == "MES06675"
        assert result[0]["rid0011"] == "SP5121"
        assert result[0]["rid0012"] == "11"

    def test_screenright_csv_quoted_msc14036_field(self):
        """msc14036 contains internal commas — must be parsed as one field."""
        result = _parse_csv_response(SAMPLE_SCREENRIGHT_CSV)
        assert len(result) == 2
        # The quoted field "SP5143,SP5153,SP5123,SP5121" must remain as one value
        assert "," in result[0]["msc14036"]
        assert result[0]["msc14036"] == "SP5143,SP5153,SP5123,SP5121"

    def test_screenright_csv_has_correct_screen_id(self):
        result = _parse_csv_response(SAMPLE_SCREENRIGHT_CSV)
        assert result[0]["rto0017"] == "INSTRUCTION_ENTRY_SCREEN"
        assert result[1]["rto0017"] == "LOT_INSTRUCTION_REGISTER_SCREEN"

    def test_header_only_csv_returns_empty_list(self):
        csv_text = "cdc0145,rid0010,rid0011\n"
        result = _parse_csv_response(csv_text)
        assert result == []

    def test_empty_string_returns_empty_list(self):
        result = _parse_csv_response("")
        assert result == []

    def test_blank_rows_are_skipped(self):
        csv_text = "cdc0145,rid0011\nABC,,\n\n"
        result = _parse_csv_response(csv_text)
        # Blank row should be skipped
        assert len(result) == 1


# ── check_user_access tests ───────────────────────────────────────────────────

class TestCheckUserAccess:
    def test_matching_payroll_and_deptcode_returns_rbac_level(self):
        result = check_user_access(PARSED_USERRIGHT, "MES06675", "SP5121")
        assert result == 11

    def test_second_user_matching_returns_rbac_level(self):
        result = check_user_access(PARSED_USERRIGHT, "ABC12345", "SP5143")
        assert result == 20

    def test_wrong_deptcode_returns_none(self):
        result = check_user_access(PARSED_USERRIGHT, "MES06675", "SP5143")
        assert result is None

    def test_wrong_payroll_returns_none(self):
        result = check_user_access(PARSED_USERRIGHT, "NOTFOUND", "SP5121")
        assert result is None

    def test_empty_data_returns_none(self):
        result = check_user_access([], "MES06675", "SP5121")
        assert result is None

    def test_pre_normalized_deptcode_matches(self):
        """JWT now stores pre-normalized deptcode; check_user_access matches directly."""
        result = check_user_access(PARSED_USERRIGHT, "MES06675", "SP5121")
        assert result == 11

    def test_both_wrong_returns_none(self):
        result = check_user_access(PARSED_USERRIGHT, "NOTFOUND", "NOTDEPT")
        assert result is None


# ── require_rbac dependency tests ─────────────────────────────────────────────

class TestRequireRbac:

    async def test_auth_mode_0_returns_none_no_redis(self):
        """AUTH_MODE=0 → no-op, returns None without touching Redis."""
        dep = require_rbac("ANY_SCREEN")
        mock_user = JWTClaims(username="test", payroll="T001", deptcode="IT")
        with patch("app.core.rbac.settings") as mock_s, \
             patch("app.core.rbac.get_redis_read") as mock_redis_read:
            mock_s.AUTH_MODE = 0
            result = await dep(user=mock_user)
            assert result is None
            mock_redis_read.assert_not_called()

    async def test_auth_mode_1_returns_none_no_redis(self):
        """AUTH_MODE=1 → no-op, returns None without touching Redis."""
        dep = require_rbac("ANY_SCREEN")
        mock_user = JWTClaims(username="test", payroll="T001", deptcode="IT")
        with patch("app.core.rbac.settings") as mock_s, \
             patch("app.core.rbac.get_redis_read") as mock_redis_read:
            mock_s.AUTH_MODE = 1
            result = await dep(user=mock_user)
            assert result is None
            mock_redis_read.assert_not_called()

    async def test_auth_mode_2_redis_hit_user_authorized(self):
        """AUTH_MODE=2 + Redis has both keys + user authorized → returns None (access granted)."""
        dep = require_rbac("LOT_INSTRUCTION_REGISTER_SCREEN")
        # JWT contains pre-normalized deptcode "SP5121"
        # MES06675 has rbac_level=11 >= min_level=10, SP5121 in allowed_depts
        user = JWTClaims(username="test", payroll="MES06675", deptcode="SP5121")

        mock_redis = MagicMock()
        mock_redis.get.side_effect = lambda key: {
            "test_app_userright": json.dumps(PARSED_USERRIGHT),
            "test_app_screenright": json.dumps(PARSED_SCREENRIGHT),
        }.get(key)

        with patch("app.core.rbac.settings") as mock_s, \
             patch("app.core.rbac.get_redis_read", return_value=mock_redis):
            mock_s.AUTH_MODE = 2
            mock_s.APP_NAME = "test_app"
            result = await dep(user=user)
            assert result is None

    async def test_auth_mode_2_rbac_level_too_low_raises_403(self):
        """AUTH_MODE=2 + rbac_level < min_level → 403."""
        dep = require_rbac("INSTRUCTION_ENTRY_SCREEN")
        # JWT contains pre-normalized deptcode "SP5121"
        # MES06675 has rbac_level=11, INSTRUCTION_ENTRY_SCREEN requires min_level=20
        user = JWTClaims(username="test", payroll="MES06675", deptcode="SP5121")

        mock_redis = MagicMock()
        mock_redis.get.side_effect = lambda key: {
            "test_app_userright": json.dumps(PARSED_USERRIGHT),
            "test_app_screenright": json.dumps(PARSED_SCREENRIGHT),
        }.get(key)

        with patch("app.core.rbac.settings") as mock_s, \
             patch("app.core.rbac.get_redis_read", return_value=mock_redis):
            mock_s.AUTH_MODE = 2
            mock_s.APP_NAME = "test_app"
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await dep(user=user)
            assert exc_info.value.status_code == 403

    async def test_auth_mode_2_dept_not_allowed_raises_403(self):
        """AUTH_MODE=2 + deptcode not in allowed_depts → 403."""
        dep = require_rbac("LOT_INSTRUCTION_REGISTER_SCREEN")
        # JWT contains pre-normalized deptcode "NOTDEPT" (not in allowed_depts)
        user = JWTClaims(username="test", payroll="ABC12345", deptcode="NOTDEPT")

        # Userright stores "NOTDEPT" so user IS found (isolates dept-not-allowed)
        userright_with_notdept = [
            {"cdc0145": "ABC12345", "rid0011": "NOTDEPT", "rid0012": "20"},
        ]

        mock_redis = MagicMock()
        mock_redis.get.side_effect = lambda key: {
            "test_app_userright": json.dumps(userright_with_notdept),
            "test_app_screenright": json.dumps(PARSED_SCREENRIGHT),
        }.get(key)

        with patch("app.core.rbac.settings") as mock_s, \
             patch("app.core.rbac.get_redis_read", return_value=mock_redis):
            mock_s.AUTH_MODE = 2
            mock_s.APP_NAME = "test_app"
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await dep(user=user)
            assert exc_info.value.status_code == 403

    async def test_auth_mode_2_user_not_found_in_userright_raises_403(self):
        """AUTH_MODE=2 + user not found in userright → 403."""
        dep = require_rbac("LOT_INSTRUCTION_REGISTER_SCREEN")
        # JWT contains pre-normalized deptcode "SP5121", but payroll NOTFOUND not in data
        user = JWTClaims(username="test", payroll="NOTFOUND", deptcode="SP5121")

        mock_redis = MagicMock()
        mock_redis.get.side_effect = lambda key: {
            "test_app_userright": json.dumps(PARSED_USERRIGHT),
            "test_app_screenright": json.dumps(PARSED_SCREENRIGHT),
        }.get(key)

        with patch("app.core.rbac.settings") as mock_s, \
             patch("app.core.rbac.get_redis_read", return_value=mock_redis):
            mock_s.AUTH_MODE = 2
            mock_s.APP_NAME = "test_app"
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await dep(user=user)
            assert exc_info.value.status_code == 403
            assert "No app access" in exc_info.value.detail

    async def test_auth_mode_2_screen_not_found_raises_403(self):
        """AUTH_MODE=2 + screen_id not in screenright → 403."""
        dep = require_rbac("NONEXISTENT_SCREEN")
        user = JWTClaims(username="test", payroll="MES06675", deptcode="SP5121")

        mock_redis = MagicMock()
        mock_redis.get.side_effect = lambda key: {
            "test_app_userright": json.dumps(PARSED_USERRIGHT),
            "test_app_screenright": json.dumps(PARSED_SCREENRIGHT),
        }.get(key)

        with patch("app.core.rbac.settings") as mock_s, \
             patch("app.core.rbac.get_redis_read", return_value=mock_redis):
            mock_s.AUTH_MODE = 2
            mock_s.APP_NAME = "test_app"
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await dep(user=user)
            assert exc_info.value.status_code == 403
            assert "NONEXISTENT_SCREEN" in exc_info.value.detail

    async def test_auth_mode_2_redis_miss_refetches_and_grants_access(self):
        """AUTH_MODE=2 + Redis miss → re-fetches BOTH endpoints → access granted."""
        dep = require_rbac("LOT_INSTRUCTION_REGISTER_SCREEN")
        # JWT contains pre-normalized deptcode "SP5121"
        user = JWTClaims(username="test", payroll="MES06675", deptcode="SP5121")

        mock_redis = MagicMock()
        # Redis returns None for both keys (cache miss)
        mock_redis.get.return_value = None

        mock_write_redis = MagicMock()

        with patch("app.core.rbac.settings") as mock_s, \
             patch("app.core.rbac.get_redis_read", return_value=mock_redis), \
             patch("app.core.rbac.get_redis_write", return_value=mock_write_redis), \
             patch("app.core.rbac._fetch_user_right", new_callable=AsyncMock, return_value=PARSED_USERRIGHT), \
             patch("app.core.rbac._fetch_screen_right", new_callable=AsyncMock, return_value=PARSED_SCREENRIGHT):
            mock_s.AUTH_MODE = 2
            mock_s.APP_NAME = "test_app"
            mock_s.RBAC_API_URL = "http://example.com"
            mock_s.RBAC_API_KEY = "test-key"
            mock_s.REDIS_EXPIRE = 10800
            result = await dep(user=user)
            assert result is None
            # Verify Redis write-back was called for both keys
            assert mock_write_redis.setex.call_count == 2

    async def test_auth_mode_2_pre_normalized_deptcode_used(self):
        """AUTH_MODE=2 + JWT contains pre-normalized deptcode → access granted."""
        dep = require_rbac("LOT_INSTRUCTION_REGISTER_SCREEN")
        # JWT contains pre-normalized "SP5121" — used directly for RBAC comparison
        user = JWTClaims(username="test", payroll="MES06675", deptcode="SP5121")

        mock_redis = MagicMock()
        mock_redis.get.side_effect = lambda key: {
            "test_app_userright": json.dumps(PARSED_USERRIGHT),
            "test_app_screenright": json.dumps(PARSED_SCREENRIGHT),
        }.get(key)

        with patch("app.core.rbac.settings") as mock_s, \
             patch("app.core.rbac.get_redis_read", return_value=mock_redis):
            mock_s.AUTH_MODE = 2
            mock_s.APP_NAME = "test_app"
            result = await dep(user=user)
            assert result is None

    async def test_auth_mode_2_redis_down_api_down_raises_503(self):
        """AUTH_MODE=2 + Redis down + RBAC API down → 503."""
        dep = require_rbac("LOT_INSTRUCTION_REGISTER_SCREEN")
        user = JWTClaims(username="test", payroll="MES06675", deptcode="SP5121")

        with patch("app.core.rbac.settings") as mock_s, \
             patch("app.core.rbac.get_redis_read", return_value=None), \
             patch("app.core.rbac.get_redis_write", return_value=None), \
             patch("app.core.rbac._fetch_user_right", new_callable=AsyncMock, side_effect=httpx.ConnectError("down")), \
             patch("app.core.rbac._fetch_screen_right", new_callable=AsyncMock, side_effect=httpx.ConnectError("down")):
            mock_s.AUTH_MODE = 2
            mock_s.APP_NAME = "test_app"
            mock_s.RBAC_API_URL = "http://example.com"
            mock_s.RBAC_API_KEY = "test-key"
            mock_s.REDIS_EXPIRE = 10800
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await dep(user=user)
            assert exc_info.value.status_code == 503
            assert "RBAC unavailable" in exc_info.value.detail
