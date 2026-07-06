"""Application configuration and settings."""

import warnings
from functools import lru_cache
from typing import Any

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class CommaSeparatedDotEnvSettingsSource(DotEnvSettingsSource):
    """Support comma-separated CORS origins in .env files."""

    def prepare_field_value(self, field_name: str, field: Any, value: Any, value_is_complex: bool) -> Any:
        if field_name == "cors_origins" and isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                return super().prepare_field_value(field_name, field, value, value_is_complex)
            return [origin.strip() for origin in raw.split(",") if origin.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # App
    app_name: str = "BiznizFlowPilot"
    debug: bool = False
    version: str = "0.1.0"

    # Database
    database_url: str = "postgresql://user:password@localhost:5432/biznizflowpilot_db"

    # JWT — no default; app raises ValidationError on startup if SECRET_KEY is not set
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    refresh_token_expiration_days: int = 7
    password_reset_token_expiration_minutes: int = 30
    invite_token_expiration_days: int = 7

    # Platform (vendor staff) JWT — deliberately a distinct signing key from
    # tenant `secret_key` so a leaked/misused tenant secret can never mint a
    # valid platform token. Defaults to reusing secret_key so rollout doesn't
    # require a new required env var; set a distinct PLATFORM_SECRET_KEY in
    # production.
    platform_secret_key: str = ""
    platform_jwt_expiration_hours: int = 8
    platform_refresh_token_expiration_days: int = 1

    @property
    def effective_platform_secret_key(self) -> str:
        """The signing key actually used for platform tokens."""
        return self.platform_secret_key or self.secret_key

    @model_validator(mode="after")
    def _guard_platform_secret_key_fallback(self) -> "Settings":
        """Fail closed in production instead of silently sharing keys.

        The empty-string fallback above exists so a fresh dev/staging
        checkout doesn't need a second required env var - but shipping that
        fallback to production silently signs platform-admin tokens with the
        same key as ordinary tenant tokens, collapsing the "separate auth
        boundary" the two token types are meant to provide. Refuse to boot
        rather than degrade silently once it matters.
        """
        if not self.platform_secret_key:
            if self.environment == "production":
                raise ValueError(
                    "PLATFORM_SECRET_KEY must be set explicitly in production - it "
                    "cannot silently fall back to SECRET_KEY once platform-admin "
                    "auth is protecting real tenant data."
                )
            warnings.warn(
                "PLATFORM_SECRET_KEY is not set; platform-admin tokens are "
                "signed with SECRET_KEY as a dev/staging convenience. Set "
                "PLATFORM_SECRET_KEY before deploying to production.",
                stacklevel=2,
            )
        return self

    # API
    api_base_url: str = "http://localhost:8000"
    api_v1_prefix: str = "/api/v1"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Environment
    environment: str = "development"  # development, staging, production

    # Redis (for future use)
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    stale_claim_check_interval_seconds: int = 60
    action_retry_check_interval_seconds: int = 60
    stale_run_check_interval_seconds: int = 300
    followup_check_interval_seconds: int = 3600  # 1 hour

    # Frontend base URL (used in emails)
    frontend_url: str = "http://localhost:3000"

    # Email delivery — set RESEND_API_KEY to use Resend; otherwise falls back to SMTP
    resend_api_key: str = ""

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    smtp_use_ssl: bool = False
    smtp_from_email: str = "no-reply@biznizflowpilot.local"
    smtp_from_name: str = "BiznizFlowPilot"
    smtp_timeout_seconds: int = 10

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100
    audit_trail_default_limit: int = 100
    audit_trail_max_limit: int = 500

    # Logging
    log_level: str = "INFO"

    # AI / LLM
    ai_provider: str = "echo"  # echo | ollama | anthropic | groq
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    ai_max_tokens: int = 1024
    ai_conversation_history_limit: int = 20

    # Agora (voice/video calling) — required for meetings/join to function;
    # no safe fallback exists (unlike secret_key) because calls cannot be
    # signed without real vendor credentials from an Agora Console project.
    agora_app_id: str = ""
    agora_app_certificate: str = ""
    agora_token_expiration_seconds: int = 3600

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings parsing to support CSV-style CORS origins."""
        return (
            init_settings,
            env_settings,
            CommaSeparatedDotEnvSettingsSource(settings_cls),
            file_secret_settings,
        )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
