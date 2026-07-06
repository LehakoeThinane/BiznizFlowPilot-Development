"""Settings tests - platform secret key fail-closed behavior."""

import pytest

from app.core.config import Settings


class TestPlatformSecretKeyFallback:
    """PLATFORM_SECRET_KEY falls back to SECRET_KEY for dev/staging
    convenience, but that fallback must never reach production silently."""

    def test_production_without_platform_secret_key_fails_closed(self):
        with pytest.raises(ValueError, match="PLATFORM_SECRET_KEY must be set explicitly in production"):
            Settings(_env_file=None, secret_key="tenant-secret", environment="production", platform_secret_key="")

    def test_production_with_platform_secret_key_boots(self):
        settings = Settings(
            _env_file=None, secret_key="tenant-secret", environment="production", platform_secret_key="platform-secret",
        )
        assert settings.effective_platform_secret_key == "platform-secret"

    def test_development_without_platform_secret_key_falls_back_with_warning(self):
        with pytest.warns(UserWarning, match="PLATFORM_SECRET_KEY is not set"):
            settings = Settings(_env_file=None, secret_key="tenant-secret", environment="development", platform_secret_key="")

        assert settings.effective_platform_secret_key == "tenant-secret"

    def test_development_with_platform_secret_key_no_warning(self):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            settings = Settings(
                _env_file=None, secret_key="tenant-secret", environment="development", platform_secret_key="platform-secret",
            )

        assert settings.effective_platform_secret_key == "platform-secret"
