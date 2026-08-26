"""
MCP Client — HTTP connection layer.

Provides:
  - MCPSessionPool     module-level pool of shared aiohttp sessions (one per server URL)
  - MCPClient          async context manager that handles handshake + query
  - CompressionHelper  decompresses gzip / zlib / lzma server responses
"""
import asyncio
import base64
import gzip
import json
import lzma
import logging
import time
import zlib
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


# ── Session Pool ──────────────────────────────────────────────────────────────

class MCPSessionPool:
    """
    Maintains one shared ``aiohttp.ClientSession`` per MCP server URL.

    Sessions (and their underlying ``TCPConnector``) are created lazily on first
    use and reused for every subsequent request — eliminating the
    "new TCP connection per query" anti-pattern.

    Call ``await pool.close_all()`` once at application shutdown.
    """

    def __init__(self):
        self._sessions: Dict[str, aiohttp.ClientSession] = {}
        self._lock = asyncio.Lock()

    async def get_session(self, server_url: str) -> aiohttp.ClientSession:
        """Return (or lazily create) the shared session for *server_url*."""
        async with self._lock:
            session = self._sessions.get(server_url)
            if session is None or session.closed:
                connector = aiohttp.TCPConnector(
                    limit=75,           # 3 servers × limit_per_host=25
                    limit_per_host=25,  # supports ~50 concurrent users with headroom
                    enable_cleanup_closed=True,
                    keepalive_timeout=30,
                )
                timeout = aiohttp.ClientTimeout(
                    total=300,
                    connect=30,
                    sock_connect=30,
                    sock_read=None,
                )
                session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers={"User-Agent": "MCP-Client/1.0"},
                )
                self._sessions[server_url] = session
                logger.info("MCPSessionPool: created shared session for %s", server_url)
            return session

    async def close_all(self) -> None:
        """Close all pooled sessions (call once at application shutdown)."""
        async with self._lock:
            for url, session in self._sessions.items():
                if not session.closed:
                    await session.close()
                    logger.info("MCPSessionPool: closed session for %s", url)
            self._sessions.clear()


# Module-level singleton — shared across all requests for the lifetime of the process
_pool = MCPSessionPool()


def get_session_pool() -> MCPSessionPool:
    """Return the module-level session pool."""
    return _pool


# ── Compression ───────────────────────────────────────────────────────────────

class CompressionHelper:
    """Decompress standardized MCP server responses (gzip / zlib / lzma)."""

    @staticmethod
    def is_compressed_response(response_data: Dict[str, Any]) -> bool:
        try:
            return response_data.get("metadata", {}).get("compression", {}).get("enabled", False)
        except (KeyError, AttributeError):
            return False

    @staticmethod
    def get_compression_info(response_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            compression = response_data.get("metadata", {}).get("compression", {})
            return {
                "enabled":          compression.get("enabled", False),
                "algorithm":        compression.get("algorithm", "none"),
                "original_size":    compression.get("original_size", 0),
                "compressed_size":  compression.get("compressed_size", 0),
                "compression_ratio":compression.get("compression_ratio", 0.0),
                "compression_time": compression.get("compression_time", 0.0),
                "encoding":         compression.get("encoding", "none"),
                "size_reduction_bytes": compression.get("size_reduction_bytes", 0),
            }
        except (KeyError, AttributeError):
            return {"enabled": False, "algorithm": "none"}

    @staticmethod
    def decompress_response(
        response_data: Dict[str, Any],
        validate_size: bool = True,
        max_decompressed_size: int = 100 * 1024 * 1024,
    ) -> Dict[str, Any]:
        """
        Decompress a standardized MCP server response.

        Returns the response_data dict with its ``data`` key replaced by the
        decompressed + JSON-parsed payload.  Returns ``response_data["data"]``
        unchanged when the response is not compressed.

        Raises:
            ValueError:   Decompression or JSON parse failure.
            RuntimeError: Decompressed size exceeds max_decompressed_size.
        """
        start_time = time.time()

        try:
            if not CompressionHelper.is_compressed_response(response_data):
                return response_data.get("data", {})

            info = CompressionHelper.get_compression_info(response_data)
            algorithm     = info["algorithm"]
            encoding      = info["encoding"]
            expected_size = info["original_size"]

            logger.info("Decompressing %s response, expected size: %s bytes", algorithm, expected_size)

            compressed_data = response_data.get("data")
            if not compressed_data:
                raise ValueError("No compressed data found in response")

            if encoding == "base64":
                try:
                    raw = base64.b64decode(compressed_data)
                except Exception as exc:
                    raise ValueError(f"Failed to decode base64 data: {exc}") from exc
            else:
                raw = (
                    compressed_data.encode("utf-8")
                    if isinstance(compressed_data, str)
                    else compressed_data
                )

            if algorithm == "gzip":
                decompressed = gzip.decompress(raw)
            elif algorithm == "zlib":
                decompressed = zlib.decompress(raw)
            elif algorithm == "lzma":
                decompressed = lzma.decompress(raw)
            else:
                raise ValueError(f"Unsupported compression algorithm: {algorithm}")

            actual_size = len(decompressed)
            if actual_size > max_decompressed_size:
                raise RuntimeError(
                    f"Decompressed size ({actual_size:,} bytes) exceeds maximum "
                    f"({max_decompressed_size:,} bytes)"
                )
            if validate_size and expected_size > 0 and actual_size != expected_size:
                logger.warning(
                    "Decompressed size mismatch: expected %s, got %s",
                    expected_size, actual_size,
                )

            try:
                result = json.loads(decompressed.decode("utf-8"))
                response_data["data"] = result
            except json.JSONDecodeError as exc:
                raise ValueError(f"Failed to parse decompressed JSON: {exc}") from exc

            logger.info(
                "Decompressed %s bytes via %s in %.4fs",
                actual_size, algorithm, time.time() - start_time,
            )
            return response_data

        except Exception as exc:
            logger.error("Decompression failed: %s", exc)
            raise ValueError(f"Decompression failed: {exc}") from exc


# ── MCPClient ─────────────────────────────────────────────────────────────────

class MCPClient:
    """
    Async context manager that manages a single MCP server session.

    Uses the module-level ``MCPSessionPool`` so the underlying
    ``aiohttp.ClientSession`` / ``TCPConnector`` is shared across all callers
    for the same *server_url* — no new TCP connection is opened per query.

    Usage::

        async with MCPClient(server_url, config_path="conf/mcpkey.json") as client:
            client.load_api_key()
            await client.initialize(client_name, client_version)
            result = await client.query_database(
                table="schema.TABLE",
                columns="*",
                conditions={"COL": "value"},
                limit=1000,
            )
    """

    def __init__(
        self,
        server_url: str,
        config_path: str = "conf/mcpkey.json",
        timeout: int = 300,
        pool: Optional[MCPSessionPool] = None,
    ):
        self.server_url   = server_url
        self.config_path  = config_path
        self.timeout      = timeout
        self._initialized = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.api_token:   Optional[str] = None
        self.server_info  = {}
        self.capabilities = {}
        self._pool        = pool or _pool

    async def __aenter__(self):
        # Borrow the shared session — do NOT create a new ClientSession/TCPConnector
        self.session = await self._pool.get_session(self.server_url)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Do NOT close — the pool owns the session lifetime
        self.session = None

    # ── Key loading ───────────────────────────────────────────────────────────

    def load_api_key(self) -> bool:
        """Load bearer token from ``config_path`` JSON file."""
        try:
            config_path = Path(self.config_path)
            if not config_path.exists():
                logger.error("MCP key file not found: %s", self.config_path)
                return False
            with open(config_path) as f:
                data = json.load(f)
            self.api_token = data.get("mcp_tokens")
            if not self.api_token:
                logger.error("No 'mcp_tokens' key in %s", self.config_path)
                return False
            return True
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.error("Failed to load MCP key: %s", exc)
            return False

    # ── Handshake ─────────────────────────────────────────────────────────────

    async def initialize(
        self,
        client_name: str = "MCP Client",
        client_version: str = "1.0.0",
    ) -> bool:
        """Send MCP initialize handshake to the server."""
        try:
            response = await self._send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": client_name, "version": client_version},
                    "capabilities": {
                        "streaming": {
                            "supported": True,
                            "protocols": ["jsonlines", "chunked", "standard"],
                        }
                    },
                },
            )
            if "result" in response:
                result = response["result"]
                self.server_info  = result.get("serverInfo", {})
                self.capabilities = result.get("capabilities", {})
                logger.info(
                    "MCP connected: %s v%s",
                    self.server_info.get("name", "unknown"),
                    self.server_info.get("version", "unknown"),
                )
                self._initialized = True
                return True
            logger.error("MCP initialization failed: %s", response)
            return False
        except Exception as exc:
            logger.error("MCP initialization error: %s", exc)
            return False

    # ── Query ─────────────────────────────────────────────────────────────────

    async def query_database(self, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Execute a query against the MCP server.

        Keyword args:
            table (str):       Required. Schema-qualified table name.
            columns (str):     Columns to select. Default ``"*"``.
            conditions (dict): WHERE conditions. Default ``None``.
            order_by (str):    ORDER BY clause. Default ``None``.
            limit (int):       Row limit. Default ``1000``.
            compression (str): Compression preference. Default ``"auto"``.

        Returns:
            Decompressed result dict, or ``None`` on failure.
        """
        if not self._initialized:
            raise RuntimeError("MCPClient not initialized — call initialize() first.")

        table      = kwargs.get("table")
        columns    = kwargs.get("columns", "*")
        conditions = kwargs.get("conditions")
        order_by   = kwargs.get("order_by")
        limit      = kwargs.get("limit", 1000)
        compression = kwargs.get("compression", "auto")

        query_params: Dict[str, Any] = {
            "table":       table,
            "columns":     columns,
            "compression": compression,
            "limit":       limit,
        }
        if conditions:
            query_params["conditions"] = conditions
        if order_by:
            query_params["order_by"] = order_by

        logger.info("MCP query: table=%s limit=%s", table, limit)

        result = await self._send_request(
            "tools/call",
            {"name": "query_database", "arguments": query_params},
        )

        if "result" not in result:
            logger.error("MCP query failed: %s", result)
            return None

        query_result = result["result"].get("query_result", {})

        if (
            isinstance(query_result, dict)
            and query_result.get("metadata", {}).get("compression", {}).get("enabled")
        ):
            query_result = CompressionHelper.decompress_response(query_result)

        if isinstance(query_result, dict):
            logger.info("MCP query complete: %s rows", query_result.get("row_count", "?"))

        return query_result

    # ── HTTP transport ────────────────────────────────────────────────────────

    async def _send_request(
        self, method: str, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        if not self.session:
            raise RuntimeError("No aiohttp session — use 'async with MCPClient(...)'")
        if not self.api_token:
            raise RuntimeError("API key not loaded — call load_api_key() first.")

        message: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id":      str(int(time.time() * 1000)),
            "method":  method,
        }
        if params:
            message["params"] = params

        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }

        async with self.session.post(
            self.server_url, data=json.dumps(message), headers=headers
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"HTTP {response.status}: {error_text}")
            result = await response.json()
            if "error" in result:
                raise Exception(f"MCP server error: {result['error']['message']}")
            return result
