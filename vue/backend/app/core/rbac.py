"""
RBAC enforcement — require_rbac(screen_id) FastAPI dependency.

Reads userright + screenright from Redis cache. On any miss, proactively
re-fetches BOTH from RBAC API and repopulates cache before checking access.

CSV column mapping (same as VueAuthService):
  userright:   cdc0145=payroll, rid0011=deptcode, rid0012=rbac_level
  screenright: rto0017=screen_id, rto0018=screen_name, rid0014=min_level, msc14036=allowed_depts
"""
import asyncio
import csv
import io
import json
import logging
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, status
from redis import Redis, RedisError

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.models import JWTClaims
from app.core.redis_client import get_redis_read, get_redis_write

logger = logging.getLogger(__name__)


# ── Thread-safe Redis helpers (blocking I/O — always called via asyncio.to_thread) ──

def _redis_read_cache(r: Redis, app_name: str) -> tuple:
    return (
        r.get(f"{app_name}_userright"),
        r.get(f"{app_name}_screenright"),
    )


def _redis_write_cache(
    w: Redis, app_name: str, expire: int, user_data, screen_data
) -> None:
    w.setex(f"{app_name}_userright",  expire, json.dumps(user_data))
    w.setex(f"{app_name}_screenright", expire, json.dumps(screen_data))


# ── CSV parsing ───────────────────────────────────────────────────────────────

def _parse_csv_response(text: str) -> list[dict]:
    """
    Parse a CSV string into a list of dicts keyed by header column names.

    Uses csv.reader to correctly handle quoted fields containing internal commas
    (e.g. msc14036 = "SP5143,SP5153,SP5123,SP5121").

    Args:
        text: Raw CSV text with header row.

    Returns:
        List of dicts, one per data row. Empty list if only header present.
    """
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []

    # First row is the header
    headers = [h.strip() for h in rows[0]]

    result = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            # Skip blank/empty rows
            continue
        record = {headers[i]: row[i].strip() for i in range(len(headers)) if i < len(row)}
        result.append(record)

    return result


# ── Access check logic ────────────────────────────────────────────────────────

def check_user_access(user_data: list[dict], payroll: str, deptcode: str) -> Optional[int]:
    """
    Look up a user's RBAC level from cached userright data.

    Scans user_data for a row where cdc0145 == payroll AND rid0011 == deptcode.
    Both must match (payroll identifies the employee; deptcode scopes the access).

    Args:
        user_data: Parsed rows from getalluseraccessright CSV.
        payroll:   User's payroll ID (from JWT claim).
        deptcode:  User's department code (from JWT claim).

    Returns:
        Integer rbac_level (from rid0012) if match found, None otherwise.
    """
    for row in user_data:
        if row.get("cdc0145") == payroll and row.get("rid0011") == deptcode:
            try:
                return int(row["rid0012"])
            except (KeyError, ValueError):
                return None
    return None


# ── RBAC API fetch ────────────────────────────────────────────────────────────

async def _fetch_user_right(api_url: str, app_name: str, api_key: str) -> list[dict]:
    """
    Fetch userright data from RBAC API.

    Args:
        api_url:  Base URL for RBAC API (no trailing slash).
        app_name: Application name registered in RBAC API.
        api_key:  API key for authentication.

    Returns:
        Parsed list of dicts from the CSV response.

    Raises:
        httpx.HTTPError: On network or HTTP error.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{api_url}/getalluseraccessright/{app_name}",
            headers={"x-api-key": api_key},
            timeout=30.0,
        )
        resp.raise_for_status()
        return _parse_csv_response(resp.text)


async def _fetch_screen_right(api_url: str, app_name: str, api_key: str) -> list[dict]:
    """
    Fetch screenright data from RBAC API.

    Args:
        api_url:  Base URL for RBAC API (no trailing slash).
        app_name: Application name registered in RBAC API.
        api_key:  API key for authentication.

    Returns:
        Parsed list of dicts from the CSV response.

    Raises:
        httpx.HTTPError: On network or HTTP error.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{api_url}/getallscreenaccessright/{app_name}",
            headers={"x-api-key": api_key},
            timeout=30.0,
        )
        resp.raise_for_status()
        return _parse_csv_response(resp.text)


# ── Cache re-fetch ────────────────────────────────────────────────────────────

async def _refetch_and_cache() -> tuple[Optional[list[dict]], Optional[list[dict]]]:
    """
    Re-fetch BOTH RBAC endpoints in parallel and write back to Redis.

    Returns:
        (userright, screenright) tuple. Both are None if RBAC API is unreachable.
        Redis write-back failure is logged as warning — does not fail the request.
    """
    try:
        user_right, screen_right = await asyncio.gather(
            _fetch_user_right(settings.RBAC_API_URL, settings.APP_NAME, settings.RBAC_API_KEY),
            _fetch_screen_right(settings.RBAC_API_URL, settings.APP_NAME, settings.RBAC_API_KEY),
        )
    except (httpx.HTTPError, httpx.TransportError) as e:
        logger.warning("RBAC API re-fetch failed: %s", e)
        return None, None

    # Write back to Redis (best-effort — failure is logged, not raised)
    w = get_redis_write()
    if w is not None:
        try:
            await asyncio.to_thread(
                _redis_write_cache, w, settings.APP_NAME,
                settings.REDIS_EXPIRE, user_right, screen_right,
            )
        except RedisError as e:
            logger.warning("Redis write-back failed after re-fetch: %s", e)
    else:
        logger.warning("Redis write client unavailable — RBAC cache not persisted for %s", settings.APP_NAME)

    return user_right, screen_right


# ── FastAPI dependency factory ────────────────────────────────────────────────

def require_rbac(screen_id: str):
    """
    FastAPI dependency factory for RBAC enforcement.

    Usage:
        @router.get("/protected")
        async def route(
            user: JWTClaims = Depends(get_current_user),
            _: None = Depends(require_rbac("SCREEN_ID")),
        ): ...

    When AUTH_MODE != 2: transparent no-op (returns None immediately).
    When AUTH_MODE == 2: checks Redis cache, proactively re-fetches on miss,
    raises 403 on access denied, 503 if RBAC data unavailable.
    """

    async def _check(user: JWTClaims = Depends(get_current_user)) -> None:
        # Step 1: No-op when AUTH_MODE != 2
        if settings.AUTH_MODE != 2:
            return None

        # Step 2: Read from Redis
        userright: Optional[list[dict]] = None
        screenright: Optional[list[dict]] = None

        r = get_redis_read()
        if r is not None:
            try:
                raw_user, raw_screen = await asyncio.to_thread(
                    _redis_read_cache, r, settings.APP_NAME
                )
                if raw_user:
                    userright = json.loads(raw_user)
                if raw_screen:
                    screenright = json.loads(raw_screen)
            except RedisError as e:
                logger.warning("Redis read error in require_rbac: %s", e)

        # Step 3: On any miss (either key None), proactively re-fetch BOTH
        if userright is None or screenright is None:
            userright, screenright = await _refetch_and_cache()

        # Step 4: If still None after re-fetch → 503
        if userright is None or screenright is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="RBAC unavailable",
            )

        # Step 5: Look up user's RBAC level
        rbac_level = check_user_access(userright, user.payroll, user.deptcode)
        if rbac_level is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No app access",
            )

        # Step 6: Find screen definition
        screen_row = next(
            (s for s in screenright if s.get("rto0017") == screen_id),
            None,
        )
        if screen_row is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Screen '{screen_id}' not found",
            )

        # Step 7: Check level and department
        try:
            min_level = int(screen_row["rid0014"])
        except (KeyError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Screen '{screen_id}' has invalid configuration",
            )

        if rbac_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient RBAC level",
            )

        raw_depts = screen_row.get("msc14036", "")
        allowed_depts = [d.strip() for d in raw_depts.split(",") if d.strip()]
        if user.deptcode not in allowed_depts:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Department not authorized for this screen",
            )

        return None

    return _check
