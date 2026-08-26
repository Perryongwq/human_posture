# backend/app/config.py
from pathlib import Path
from functools import lru_cache
from typing import Tuple, Type

from pydantic_settings import BaseSettings, JsonConfigSettingsSource, PydanticBaseSettingsSource


_CONF_FILE = Path(__file__).resolve().parents[2] / "conf" / "maincfg.json"


class Settings(BaseSettings):
    """
    Application settings loaded from conf/maincfg.json.
    JWT_JWE_KEY is required — app will not start without it.
    """
    # ── Required (no defaults — startup fails if absent) ──────────
    JWT_JWE_KEY: str      # base64url-encoded 32-byte key — decrypts app JWE (shared with VueAuthService)

    # ── Optional with defaults ─────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"  # kept for backward compat — not used after JWE migration
    CORS_ORIGINS: list[str] = []
    CORS_ORIGIN_REGEX: str = ""
    AUTH_MODE: int = 1  # 0=off | 1=sso | 2=sso+rbac

    # ── RBAC fields (required only when AUTH_MODE=2) ──────────────
    APP_NAME: str = ""
    APP_SCREEN_ID: str = ""          # Screen ID for /api/whoami example route
    RBAC_API_URL: str = ""
    RBAC_API_KEY: str = ""
    REDIS_HOST: str = ""
    REDIS_WRITE_PORT: int = 6379
    REDIS_READ_PORT: int = 6380
    REDIS_PASS: str = ""
    REDIS_EXPIRE: int = 3600        # 1 hour

    # ── Local VLM (Ollama) — station-label reading, see routers/posture.py ──
    OLLAMA_URL: str = "http://127.0.0.1:11434"   # 127.0.0.1, not localhost: Docker/WSL squat on ::1 here
    OLLAMA_VISION_MODEL: str = "qwen3-vl:8b"

    # ── RabbitMQ / insert queue ───────────────────────────────────────
    PIKA_HOST: str = ""
    PIKA_PORT: int = 5672
    PIKA_USER: str = ""
    PIKA_PASS: str = ""
    PIKA_TOKEN: str = ""         # security token included in every queue payload

    PIKA_VHOST: str = "/"        # queue 1 (default)
    PIKA_QUEUE: str = ""         # queue 1 (default)
    PIKA_VHOST_2: str = ""       # queue 2 (optional)
    PIKA_QUEUE_2: str = ""       # queue 2 (optional)

    # Activity log queue — records every endpoint access
    PIKA_VUE_VHOST: str = ""
    PIKA_VUE_QUEUE: str = ""

    model_config = {"extra": "ignore"}

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[PydanticBaseSettingsSource],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            JsonConfigSettingsSource(settings_cls, json_file=_CONF_FILE),
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Parsed once at startup."""
    return Settings()


settings = get_settings()
