"""
Redis connection manager — dual-pool (read/write) with lazy init.

Pools are created on first use (first AUTH_MODE=2 request), not at startup.
If Redis is unreachable, functions return None — callers must handle gracefully.
"""
import logging
from typing import Optional

from redis import Redis, ConnectionPool, RedisError

logger = logging.getLogger(__name__)

# Module-level state (lazy — None until init_redis_pools called)
_initialized: bool = False
_write_client: Optional[Redis] = None
_read_client: Optional[Redis] = None


def init_redis_pools(host: str, write_port: int, read_port: int, password: str) -> None:
    """
    Initialize separate read/write connection pools.

    Called automatically on first get_redis_write/read call.
    Logs warning if either pool fails to connect — does NOT raise.
    """
    global _initialized, _write_client, _read_client
    _initialized = True

    # Write pool
    try:
        write_pool = ConnectionPool(
            host=host,
            port=write_port,
            password=password,
            db=0,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            max_connections=20,
            retry_on_timeout=True,
        )
        client = Redis(connection_pool=write_pool)
        client.ping()
        _write_client = client
        logger.info("Redis write pool connected (port %d)", write_port)
    except RedisError as e:
        _write_client = None
        logger.warning("Redis write pool unavailable (port %d): %s", write_port, e)

    # Read pool
    try:
        read_pool = ConnectionPool(
            host=host,
            port=read_port,
            password=password,
            db=0,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            max_connections=20,
            retry_on_timeout=True,
        )
        client = Redis(connection_pool=read_pool)
        client.ping()
        _read_client = client
        logger.info("Redis read pool connected (port %d)", read_port)
    except RedisError as e:
        _read_client = None
        logger.warning("Redis read pool unavailable (port %d): %s", read_port, e)


def _ensure_initialized() -> None:
    """Lazy init: create pools on first use using current settings."""
    global _initialized
    if _initialized:
        return
    from app.core.config import get_settings
    s = get_settings()
    if not s.REDIS_HOST:
        _initialized = True  # Mark as attempted — no host configured
        logger.warning("REDIS_HOST not configured — Redis disabled")
        return
    init_redis_pools(s.REDIS_HOST, s.REDIS_WRITE_PORT, s.REDIS_READ_PORT, s.REDIS_PASS)


def get_redis_write() -> Optional[Redis]:
    """Return write Redis client, or None if unavailable."""
    _ensure_initialized()
    return _write_client


def get_redis_read() -> Optional[Redis]:
    """Return read Redis client, or None if unavailable."""
    _ensure_initialized()
    return _read_client


def close_redis_pools() -> None:
    """Close both Redis connection pools — call once at application shutdown."""
    global _write_client, _read_client
    for label, client in [("write", _write_client), ("read", _read_client)]:
        if client is not None:
            try:
                client.close()
                logger.info("Redis %s pool closed", label)
            except Exception as exc:
                logger.warning("Error closing Redis %s pool: %s", label, exc)
    _write_client = None
    _read_client = None


def reset_redis_state() -> None:
    """Reset module state — used only in tests."""
    global _initialized, _write_client, _read_client
    _initialized = False
    _write_client = None
    _read_client = None
