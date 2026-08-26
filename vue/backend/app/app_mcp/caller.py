"""
MCP caller layer — retry, circuit breaker, and caller_func.

caller_func() is the single entry point routers should use to query a database
via MCP.  It handles:
  - Server URL selection by db name ("prass" | "eprass" | "eprass19c")
  - Circuit breaker protection (prevents cascading failures)
  - Exponential backoff retry (transient errors only)
  - Smart error classification (permanent errors are not retried)

Usage::

    from app.app_mcp.caller import caller_func
    from app.app_mcp.config import load_mcp_config

    config = load_mcp_config()

    result = await caller_func(
        config,
        table_name="schema.MY_TABLE",
        columns="COL1, COL2",
        condition={"KEY_COL": some_value},
        order_by="COL1 ASC",
        limit=500,
        db="prass",
    )

    # result["data"]["columns"] — list of column names
    # result["data"]["rows"]    — list of row arrays
"""
import asyncio
import logging
import pprint
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional

from icecream import ic
from app.app_mcp.client import MCPClient

# Keep lists/rows on a single line — much easier to read in the console
ic.configureOutput(
    argToStringFunction=lambda x: pprint.pformat(x, width=180, compact=True)
)

logger = logging.getLogger(__name__)


# ── Error classification ──────────────────────────────────────────────────────

class PermanentDatabaseError(Exception):
    """
    Permanent error — bad SQL, missing table/column, permission denied.
    These are NOT retried and do NOT count against the circuit breaker.
    """


class TransientDatabaseError(Exception):
    """
    Transient error — network timeout, connection lost, deadlock.
    These ARE retried with exponential backoff.
    """


def classify_database_error(error_message: str) -> type:
    """Return PermanentDatabaseError or TransientDatabaseError based on message."""
    msg = str(error_message).lower()

    permanent_patterns = [
        "ora-00904", "ora-00942", "ora-00911", "ora-00933", "ora-00936",
        "ora-01031", "ora-01722", "ora-01858",
        "invalid identifier", "table or view does not exist",
        "does not exist or is not accessible", "does not exist",
        "syntax error", "column does not exist", "permission denied",
        "not a valid month", "not a valid day", "not a valid year",
    ]
    transient_patterns = [
        "ora-03113", "ora-03114", "ora-03135",
        "ora-12150", "ora-12153", "ora-12154", "ora-12514",
        "ora-12541", "ora-12543", "ora-12545",
        "ora-00060",
        "connection timeout", "connection refused", "connection reset",
        "network error", "timeout", "temporarily unavailable", "resource busy",
    ]

    for pattern in permanent_patterns:
        if pattern in msg:
            return PermanentDatabaseError

    for pattern in transient_patterns:
        if pattern in msg:
            return TransientDatabaseError

    return TransientDatabaseError  # unknown → assume transient (safer to retry)


# ── Circuit breaker ───────────────────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED    = "closed"     # Normal — requests pass through
    OPEN      = "open"       # Too many failures — reject immediately
    HALF_OPEN = "half_open"  # One probe request allowed


class CircuitBreaker:
    """
    Prevents cascading failures when a database/MCP server is unhealthy.

    - CLOSED   → normal operation
    - OPEN     → rejects requests immediately for ``recovery_timeout`` seconds
    - HALF_OPEN→ allows one probe; reopens on failure, closes on success

    Permanent errors (bad SQL, missing columns) do NOT count toward the
    failure threshold — only transient errors do.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout:  int = 60,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self.failure_count     = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
        self._probe_in_flight: bool = False  # guards HALF_OPEN single-probe invariant

    async def call_async(self, func: Callable, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker → HALF_OPEN")
            else:
                raise Exception(
                    f"Circuit breaker OPEN — service unavailable. "
                    f"Retry after {self.recovery_timeout}s."
                )

        # HALF_OPEN: allow exactly one probe; reject all concurrent requests
        if self.state == CircuitState.HALF_OPEN:
            if self._probe_in_flight:
                raise Exception(
                    "Circuit breaker HALF_OPEN — probe already in flight. Try again shortly."
                )
            self._probe_in_flight = True

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except PermanentDatabaseError:
            logger.debug("Circuit breaker: permanent error ignored (not a failure)")
            raise
        except Exception:
            self._on_failure()
            raise
        finally:
            self._probe_in_flight = False

    def _should_attempt_reset(self) -> bool:
        if self.last_failure_time is None:
            return False
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _on_success(self):
        if self.failure_count > 0:
            logger.info("Circuit breaker → CLOSED (recovered)")
        self.failure_count     = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def _on_failure(self):
        self.failure_count    += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                "Circuit breaker → OPEN after %d transient failures. "
                "Recovery in %ds.",
                self.failure_count, self.recovery_timeout,
            )

    def reset(self):
        old = self.state
        self.failure_count     = 0
        self.last_failure_time = None
        self._probe_in_flight  = False
        self.state = CircuitState.CLOSED
        if old != CircuitState.CLOSED:
            logger.info("Circuit breaker manually reset → CLOSED (was %s)", old.value)

    def get_status(self) -> dict:
        return {
            "state":             self.state.value,
            "failure_count":     self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
            "recovery_timeout":  self.recovery_timeout,
        }


# One circuit breaker per database — shared across all requests
circuit_breakers: Dict[str, CircuitBreaker] = {
    "prass":     CircuitBreaker(failure_threshold=5, recovery_timeout=60),
    "eprass":    CircuitBreaker(failure_threshold=5, recovery_timeout=60),
    "eprass19c": CircuitBreaker(failure_threshold=5, recovery_timeout=60),
}


def get_all_circuit_breaker_status() -> dict:
    """Return status dict for all circuit breakers (useful for a /health route)."""
    return {db: cb.get_status() for db, cb in circuit_breakers.items()}


def reset_circuit_breaker(db: Optional[str] = None) -> dict:
    """Reset one or all circuit breakers to CLOSED state."""
    if db is None:
        for cb in circuit_breakers.values():
            cb.reset()
        return {"status": "success", "message": "All circuit breakers reset"}
    if db in circuit_breakers:
        circuit_breakers[db].reset()
        return {"status": "success", "message": f"Circuit breaker for '{db}' reset"}
    return {"status": "error", "message": f"Unknown database: '{db}'"}


# ── Retry decorator ───────────────────────────────────────────────────────────

def async_retry_with_backoff(
    max_retries:      int   = 3,
    initial_delay:    float = 1.0,
    max_delay:        float = 30.0,
    exponential_base: float = 2.0,
    exceptions:       tuple = (Exception,),
    smart_retry:      bool  = True,
):
    """
    Decorator: retry an async function with exponential backoff.

    When ``smart_retry=True``, permanent database errors (bad SQL, missing
    tables/columns) raise immediately without retrying.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exc = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if smart_retry:
                        if classify_database_error(str(exc)) == PermanentDatabaseError:
                            logger.error(
                                "%s permanent error (no retry): %s",
                                func.__name__, exc,
                            )
                            raise PermanentDatabaseError(str(exc)) from exc

                    if attempt == max_retries:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func.__name__, max_retries + 1, exc,
                        )
                        raise

                    wait = min(delay, max_delay)
                    logger.warning(
                        "%s attempt %d/%d failed (transient): %s — retrying in %.1fs",
                        func.__name__, attempt + 1, max_retries + 1, exc, wait,
                    )
                    await asyncio.sleep(wait)
                    delay *= exponential_base

            if last_exc:
                raise last_exc

        return wrapper
    return decorator


# ── Internal query executor (with retry) ─────────────────────────────────────

@async_retry_with_backoff(
    max_retries=3,
    initial_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    exceptions=(Exception,),
    smart_retry=True,
)
async def _execute_query(
    client,
    columns:    Any,
    table_name: str,
    order_by:   Optional[str],
    conditions: Optional[Dict],
    limit:      int,
) -> Dict[str, Any]:
    result = await client.query_database(
        columns=str(columns),
        table=str(table_name),
        order_by=order_by if order_by else None,
        conditions=conditions if conditions else None,
        limit=limit,
    )
    if not result:
        raise Exception("Query returned no result")
    return result


# ── Public entry point ────────────────────────────────────────────────────────

async def caller_func(
    config:     Dict[str, Any],
    table_name: str,
    columns:    Any = "*",
    condition:  Optional[Dict] = None,
    order_by:   Optional[str]  = None,
    limit:      int  = 1000,
    db:         str  = "prass",
) -> Optional[Dict[str, Any]]:
    """
    Query a database through the MCP server with circuit-breaker + retry protection.

    Args:
        config:     MCP config dict loaded from ``conf/mcp_setting.json``.
                    Required keys: PRASS_MCP_SERVER, EPRASS_MCP_SERVER,
                    MCP_SERVER_EPRASS_19C, CLIENT_NAME, CLIENT_VERSION,
                    APIKEY_PATH, APP_NAME.
        table_name: Schema-qualified table/view name (e.g. ``"prass.MY_TABLE"``).
        columns:    Column list or ``"*"``. Default ``"*"``.
        condition:  WHERE conditions dict  e.g. ``{"COL": "value"}``.
        order_by:   ORDER BY string e.g. ``"DATE_COL ASC"``.
        limit:      Max rows to return. Default ``1000``.
        db:         Target database: ``"prass"`` | ``"eprass"`` | ``"eprass19c"``.

    Returns:
        Result dict with keys ``data.columns`` and ``data.rows``, or ``None``
        on unrecoverable failure.

    Result shape::

        {
          "data": {
            "columns": ["COL1", "COL2", ...],
            "rows":    [[val1, val2, ...], ...]
          },
          "row_count": 42,
          ...
        }
    """
    funcname = "caller_func"
    logger.info("%s started: table=%s db=%s", funcname, table_name, db)
    ic(table_name, columns, condition, order_by, limit, db)

    try:
        if db == "eprass":
            server_url = config["EPRASS_MCP_SERVER"]
        elif db == "eprass19c":
            server_url = config["MCP_SERVER_EPRASS_19C"]
        else:
            server_url = config["PRASS_MCP_SERVER"]

        cb = circuit_breakers.get(db)
        if cb is None:
            logger.warning("No circuit breaker for db=%s — creating one", db)
            cb = CircuitBreaker()
            circuit_breakers[db] = cb

        async def _query():
            async with MCPClient(server_url, config_path=config["APIKEY_PATH"]) as client:
                if not client.load_api_key():
                    raise Exception("Failed to load MCP API key")
                if not await client.initialize(config["CLIENT_NAME"], config["CLIENT_VERSION"]):
                    raise Exception("Failed to initialize MCP client")
                return await _execute_query(
                    client, columns, table_name, order_by, condition, limit
                )

        result = await cb.call_async(_query)
        logger.info(
            "%s completed: %s rows from %s",
            funcname, result.get("row_count", "?"), table_name,
        )
        ic(result)
        return result

    except PermanentDatabaseError as exc:
        logger.warning(
            "%s permanent error for table=%s db=%s: %s",
            funcname, table_name, db, exc,
        )
        ic(f"PERMANENT ERROR — {table_name} [{db}]: {exc}")
        return None

    except Exception as exc:
        logger.error(
            "%s failed for table=%s db=%s: %s",
            funcname, table_name, db, exc,
        )
        ic(f"ERROR — {table_name} [{db}]: {exc}")
        return None
