# backend/tests/test_config.py
"""Tests for config module — BE-06, CFG-01."""
import os


class TestSettings:
    """BE-06: Settings loads from conf/maincfg.json (env vars override JSON)."""

    def test_settings_loads_jwe_key_from_env(self):
        """JWT_JWE_KEY from environment variable overrides maincfg.json."""
        from app.core.config import settings
        from tests.conftest import TEST_APP_JWE_KEY_B64
        # conftest.py sets JWT_JWE_KEY env var before app imports — env takes priority
        assert settings.JWT_JWE_KEY == TEST_APP_JWE_KEY_B64

    def test_settings_auth_mode_class_default_is_1(self):
        """AUTH_MODE class field default is 1 (SSO enabled)."""
        from app.core.config import Settings
        assert Settings.model_fields["AUTH_MODE"].default == 1


class TestGitignore:
    """CFG-01: conf/maincfg.json is gitignored (contains secrets)."""

    def test_maincfg_not_tracked(self):
        """Verify conf/maincfg.json is in .gitignore."""
        gitignore_path = os.path.join(
            os.path.dirname(__file__), "..", ".gitignore"
        )
        with open(gitignore_path) as f:
            content = f.read()
        assert "maincfg.json" in content
