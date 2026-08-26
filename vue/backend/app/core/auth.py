# backend/app/auth.py
# ═══════════════════════════════════════════════════════════════════
# Auth seam for VueAuthService JWE integration
# Version: 2.0 | Upgraded from JWT (HS256) to JWE (dir/A256GCM)
# Token is now encrypted — payload unreadable without JWT_JWE_KEY
# ═══════════════════════════════════════════════════════════════════
import base64
import json
import time
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwcrypto import jwe, jwk
from jwcrypto.jwe import InvalidJWEData

from app.core.config import settings
from app.core.models import JWTClaims

# auto_error=False: missing Authorization header → credentials=None → 401 (not 422)
security = HTTPBearer(auto_error=False)

# Mock claims returned when AUTH_MODE=0
_MOCK_CLAIMS = JWTClaims(username="dev", payroll="DEV001", deptcode="IT")

# Cache the JWE key at module level (loaded once)
_app_jwe_key = None


def _get_app_jwe_key() -> jwk.JWK:
    global _app_jwe_key
    if _app_jwe_key is None:
        key_bytes = base64.urlsafe_b64decode(settings.JWT_JWE_KEY + "==")
        k_val = base64.urlsafe_b64encode(key_bytes).rstrip(b"=").decode()
        _app_jwe_key = jwk.JWK(kty="oct", k=k_val)
    return _app_jwe_key


def _decrypt_jwe(token_str: str) -> dict:
    """Decrypt app JWE and return claims. Raises ValueError on any failure."""
    try:
        d = jwe.JWE()
        d.deserialize(token_str, _get_app_jwe_key())
        claims = json.loads(d.payload)
    except (InvalidJWEData, json.JSONDecodeError, UnicodeDecodeError, ValueError, KeyError) as e:
        raise ValueError(f"JWE decryption failed: {e}")

    if claims.get("exp", 0) < int(time.time()):
        raise ValueError("Token has expired")

    return claims


def try_extract_user(token: str) -> tuple[str | None, str | None]:
    """
    Best-effort JWE decode. Returns (payroll, username) or (None, None).
    Never raises — intended for non-critical callers such as activity logging.
    """
    try:
        claims = _decrypt_jwe(token)
        return claims.get("payroll"), claims.get("username")
    except Exception:
        return None, None


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> JWTClaims:
    """
    FastAPI dependency. Inject into any route with: Depends(get_current_user)

    Returns JWTClaims on success. Raises 401 on missing/invalid/expired token.
    When AUTH_MODE=0, returns mock claims without touching the token.
    """
    # AUTH_MODE=0: bypass for development / non-auth deployments
    if settings.AUTH_MODE == 0:
        return _MOCK_CLAIMS

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = _decrypt_jwe(credentials.credentials)
        return JWTClaims(
            username=payload["username"],
            payroll=payload["payroll"],
            deptcode=payload["deptcode"],
        )
    except ValueError as e:
        msg = str(e).lower()
        detail = "Token expired" if "expired" in msg else "Invalid token"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
