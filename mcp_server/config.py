"""MCP server configuration - loaded from the repo's .env file.

Deliberately reads credentials from .env only (not from .mcp.json's `env`
block too) so BFP_MCP_EMAIL/PASSWORD are written down in exactly one
gitignored, plaintext file, not duplicated across two.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BFP_MCP_", case_sensitive=False, extra="ignore")

    base_url: str = "http://127.0.0.1:8000"
    email: str = Field(..., description="BFP login for the dedicated MCP service account")
    password: str = Field(..., description="Password for that account")

    # How long an identical (tool_name, args) call is deduped for - see
    # mcp_server/idempotency.py. Covers the "httpx timeout, did it actually
    # apply?" retry window without caching indefinitely.
    idempotency_window_seconds: int = 30

    # Hard cap applied to every generated list_* tool regardless of what the
    # underlying endpoint's own max page size allows - see tool_registry.py.
    list_tool_page_size: int = 50

    # Session-level circuit breaker: per-call approval protects against one
    # bad call, not a sequence of many small ones (approval fatigue, or a
    # prompt-injection chain that gets a human rubber-stamping a string of
    # individually-plausible actions that add up to something bad
    # collectively). After this many severe/destructive-tier calls succeed
    # in one process lifetime, the server refuses any further ones - the
    # human has to notice and restart the MCP connection (a real,
    # out-of-band action) to reset it. See server.py's CircuitBreaker.
    max_destructive_calls_per_session: int = 15


def load_settings() -> MCPSettings:
    """Load settings, failing fast with a clear message if credentials are missing.

    Bare pydantic-settings ValidationErrors are a wall of internal field
    metadata - this reformats the common "you forgot to set .env" case into
    something actionable before it ever reaches server startup.
    """
    try:
        return MCPSettings()
    except Exception as exc:  # pydantic ValidationError
        raise RuntimeError(
            "mcp_server is missing required configuration. Add to a .env file "
            "in the repo root:\n"
            "  BFP_MCP_BASE_URL=http://127.0.0.1:8000\n"
            "  BFP_MCP_EMAIL=<the dedicated MCP service account's login>\n"
            "  BFP_MCP_PASSWORD=<its password>\n"
            f"(underlying error: {exc})"
        ) from exc
