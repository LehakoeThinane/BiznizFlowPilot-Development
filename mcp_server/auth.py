"""Bearer-token management for the MCP server's own BFP login.

The dedicated service account behind BFP_MCP_EMAIL/PASSWORD must be role
`manager` - see the "Defense in depth" discussion in the plan this package
implements. `staff` was the first choice for free finance/hr/payroll
denial, but app/api/invoice.py and app/api/invites.py both gate every
mutating endpoint behind PRIVILEGED_ROLES ({"owner","manager"}), which
`staff` fails - so with `staff` every invoice/invite write tool would be
generated, approved by the user, and then 403. `manager` is required for
the v1 write scope to actually work; that in turn means router_policy.py
carries finance/hr/payroll/billing exclusion alone, with no role-layer
backstop - see mcp_server/router_policy.py's module docstring.
"""

from __future__ import annotations

import time

import httpx

from mcp_server.config import MCPSettings

_LOGIN_PATH = "/api/v1/auth/login"
_REFRESH_PATH = "/api/v1/auth/refresh"
# Refresh this many seconds before actual expiry, so a call in flight doesn't
# race an access token that expires mid-request.
_REFRESH_SKEW_SECONDS = 60


class AuthError(RuntimeError):
    """Raised when login or refresh fails outright (bad credentials, backend down)."""


class TokenStore:
    """Holds the current access/refresh token pair, refreshing as needed."""

    def __init__(self, settings: MCPSettings, http_client: httpx.Client | None = None):
        self._settings = settings
        # Only used for the auth endpoints themselves - the tool-call path
        # uses mcp_server/client.py's own client with the resulting bearer
        # token attached.
        self._http = http_client or httpx.Client(base_url=settings.base_url, timeout=15.0)
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._access_expires_at: float = 0.0

    def get_valid_access_token(self) -> str:
        """Return a currently-valid access token, logging in/refreshing as needed."""
        if self._access_token and time.monotonic() < self._access_expires_at - _REFRESH_SKEW_SECONDS:
            return self._access_token

        if self._refresh_token:
            try:
                self._refresh()
                return self._access_token  # type: ignore[return-value]
            except AuthError:
                pass  # refresh token itself expired/invalid - fall through to a fresh login

        self._login()
        return self._access_token  # type: ignore[return-value]

    def _login(self) -> None:
        try:
            resp = self._http.post(
                _LOGIN_PATH, json={"email": self._settings.email, "password": self._settings.password}
            )
        except httpx.RequestError as exc:
            raise AuthError(
                f"Could not reach BFP backend at {self._settings.base_url} to log in - is it running "
                "(scripts/start-backend.ps1)? Underlying error: " + str(exc)
            ) from exc

        if resp.status_code != 200:
            raise AuthError(
                f"BFP login failed ({resp.status_code}): {_extract_detail(resp)}. "
                "Check BFP_MCP_EMAIL/BFP_MCP_PASSWORD in .env."
            )
        self._store_tokens(resp.json())

    def _refresh(self) -> None:
        try:
            resp = self._http.post(_REFRESH_PATH, json={"refresh_token": self._refresh_token})
        except httpx.RequestError as exc:
            raise AuthError(f"Could not reach BFP backend to refresh token: {exc}") from exc

        if resp.status_code != 200:
            raise AuthError(f"Refresh failed ({resp.status_code}): {_extract_detail(resp)}")
        self._store_tokens(resp.json())

    def _store_tokens(self, payload: dict) -> None:
        self._access_token = payload["access_token"]
        self._refresh_token = payload["refresh_token"]
        self._access_expires_at = time.monotonic() + payload["expires_in"]


def _extract_detail(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("detail", resp.text))
    except ValueError:
        return resp.text
