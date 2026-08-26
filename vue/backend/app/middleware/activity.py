"""
Activity log middleware — records every HTTP request to the activity_log queue.

Captured per request:
  - IP address  (X-Forwarded-For → client.host fallback)
  - HTTP method
  - Route path
  - Payroll + username from JWT (when available; empty when AUTH_MODE=0 or unauthenticated)

Skipped:
  - OPTIONS  (CORS preflight — no meaningful user action)
  - /health  (liveness probe — high-frequency noise)

The log is fire-and-forget: published in a background thread after the response
is sent. A publish failure is logged as a warning and never surfaces to the client.

Implementation note:
  Pure ASGI middleware (not BaseHTTPMiddleware) to avoid streaming-response issues
  and to ensure asyncio.create_task() always has an active event loop.
"""
import asyncio
import logging

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings

logger = logging.getLogger(__name__)

_SKIP_PATHS = frozenset({"/health"})
_SKIP_METHODS = frozenset({"OPTIONS"})

# Strong references to in-flight fire-and-forget tasks.
# Auto-discarded via done_callback when each task completes.
_background_tasks: set[asyncio.Task] = set()


class ActivityLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        if request.method in _SKIP_METHODS or request.url.path in _SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        ip = _get_ip(request)
        payroll, username = _extract_user(request)

        # Process the request — response is sent to the client here
        await self.app(scope, receive, send)

        # Fire-and-forget after response — never delays the client
        task = asyncio.create_task(
            _publish_log(ip, request.method, request.url.path, payroll, username)
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)


def _get_ip(request: Request) -> str:
    """Return the real client IP, honouring X-Forwarded-For for reverse-proxy setups."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _extract_user(request: Request) -> tuple[str | None, str | None]:
    """
    Best-effort user extraction from the Authorization header.

    AUTH_MODE=0: returns mock dev values so dev activity is still visible in the log.
    No token / bad token: returns (None, None) — logged as anonymous.
    """
    if settings.AUTH_MODE == 0:
        return "DEV001", "dev"

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, None

    from app.core.auth import try_extract_user
    return try_extract_user(auth[7:])


async def _publish_log(
    ip: str,
    method: str,
    route: str,
    payroll: str | None,
    username: str | None,
) -> None:
    """Run the blocking pika publish in a thread pool. Silently handles all errors."""
    try:
        await asyncio.to_thread(_sync_publish, ip, method, route, payroll, username)
    except Exception as exc:
        logger.warning("Activity log background task failed: %s", exc)


def _sync_publish(
    ip: str,
    method: str,
    route: str,
    payroll: str | None,
    username: str | None,
) -> None:
    from app.queue.activity import log_activity
    log_activity(ip, method, route, payroll, username)
