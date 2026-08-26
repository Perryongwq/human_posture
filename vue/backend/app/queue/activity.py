"""
Activity log publisher — sends endpoint access records to the activity_log queue.

Each record contains:
  - app_name     : application name from APP_NAME in .env (identifies source app)
  - ip_address   : client IP (honours X-Forwarded-For)
  - http_method  : GET / POST / etc.
  - route        : URL path  e.g. /api/whoami
  - payroll      : employee ID from JWT (empty string when unauthenticated)
  - username     : display name from JWT (empty string when unauthenticated)
  - log_datetime : UTC timestamp

The queue is configured via PIKA_VUE_VHOST / PIKA_VUE_QUEUE in .env.
If those settings are empty, logging is silently disabled.
"""

import json
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.queue.connection import AmqpConnection

logger = logging.getLogger(__name__)

# ── SQL ───────────────────────────────────────────────────────────────────────
# TODO: update schema + table to match DB
_SQL_ACTIVITY_LOG = (
    "INSERT INTO YOUR_SCHEMA.ACTIVITY_LOG "
    "(APP_NAME, IP_ADDRESS, HTTP_METHOD, ROUTE, PAYROLL, USERNAME, LOG_DATETIME) "
    "VALUES (:1, :2, :3, :4, :5, :6, TO_DATE(:7, 'YYYY/MM/DD HH24:MI:SS'))"
)


def log_activity(
    ip: str,
    method: str,
    route: str,
    payroll: str | None,
    username: str | None,
) -> None:
    """
    Publish one activity log entry to the activity_log queue.

    Uses AmqpConnection.send_message() directly — opens a fresh connection,
    publishes with confirm_delivery, then closes. No persistent connection needed
    since this is called once per request.

    Silently swallows all errors so a queue failure never disrupts the app.
    """
    if not settings.PIKA_VUE_VHOST or not settings.PIKA_VUE_QUEUE:
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M:%S")
    payload = json.dumps({
        "sql": _SQL_ACTIVITY_LOG,
        "data": [[
            settings.APP_NAME,
            ip,
            method,
            route,
            payroll or "",
            username or "",
            timestamp,
        ]],
    })

    conn = AmqpConnection(
        hostname=settings.PIKA_HOST,
        port=settings.PIKA_PORT,
        username=settings.PIKA_USER,
        password=settings.PIKA_PASS,
        vhosts=settings.PIKA_VUE_VHOST,
        routingkeys=settings.PIKA_VUE_QUEUE,
    )
    try:
        conn.send_message(payload)
        logger.debug(
            "Activity logged: %s %s | app=%s | user=%s | ip=%s",
            method, route, settings.APP_NAME, payroll or "anon", ip,
        )
    except Exception as exc:
        logger.warning("log_activity publish failed: %s", exc)
