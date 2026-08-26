"""
MCP config loader.

Reads conf/mcp_setting.json and returns the dict expected by caller_func().
CLIENT_NAME is automatically sourced from APP_NAME in settings (.env) so
developers never need to touch this file.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path("conf/mcp_setting.json")


@lru_cache(maxsize=1)
def load_mcp_config(path: str = str(_DEFAULT_PATH)) -> Dict[str, Any]:
    """
    Load and cache MCP configuration from a JSON file.

    CLIENT_NAME is injected automatically from ``APP_NAME`` in ``.env`` —
    no manual edits to the JSON file are needed.

    Args:
        path: Path to the JSON config file. Defaults to ``conf/mcp_setting.json``.

    Returns:
        Config dict with keys: PRASS_MCP_SERVER, EPRASS_MCP_SERVER,
        MCP_SERVER_EPRASS_19C, CLIENT_NAME, CLIENT_VERSION, APIKEY_PATH.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError:        If the JSON is malformed or required keys are missing.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"MCP config not found: {config_path}. "
            "Ensure conf/mcp_setting.json exists."
        )

    try:
        with open(config_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {config_path}: {exc}") from exc

    required_keys = [
        "PRASS_MCP_SERVER",
        "EPRASS_MCP_SERVER",
        "MCP_SERVER_EPRASS_19C",
        "CLIENT_VERSION",
        "APIKEY_PATH",
    ]
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ValueError(f"Missing required keys in {config_path}: {missing}")

    # CLIENT_NAME is sourced from APP_NAME in .env — single source of truth
    config["CLIENT_NAME"] = settings.APP_NAME

    logger.info(
        "MCP config loaded from %s (CLIENT_NAME=%s)",
        config_path, config["CLIENT_NAME"],
    )
    return config
