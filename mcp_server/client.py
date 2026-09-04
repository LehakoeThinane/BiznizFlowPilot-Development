"""Thin, sanitizing HTTP wrapper around the BFP REST API.

Every MCP tool call ultimately goes through BFPClient.request(). Two
behaviors that are load-bearing, not incidental:

- Only 401/403/422/404 forward the backend's own `detail` message verbatim.
  Any >= 500 response is replaced with a fixed generic string before it
  reaches the model. FastAPI's default 500 body / an unhandled exception's
  traceback can contain internal file paths or stack frames - there is no
  reason to let that leak into a model's context or a response shown to the
  user. This is a must-ship item, not a nice-to-have (see the plan's "V1
  must-ship checklist").
- Callers get back a plain dict/list (parsed JSON) or a ToolError - never a
  raw httpx.Response - so tool_registry.py's executors don't each have to
  remember to sanitize.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from mcp_server.auth import TokenStore

_PASSTHROUGH_STATUSES = {401, 403, 404, 422}
_GENERIC_SERVER_ERROR = "BFP backend error - check server logs on the machine running the backend."


@dataclass
class ToolError(Exception):
    """Raised for any non-2xx response; carries a message safe to show the model."""

    status_code: int
    message: str

    def __str__(self) -> str:
        return f"[{self.status_code}] {self.message}"


class BFPClient:
    def __init__(self, base_url: str, token_store: TokenStore, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._tokens = token_store
        self._http = httpx.Client(base_url=self._base_url, timeout=timeout)

    def request(
        self, method: str, path: str, *, params: dict | None = None, json_body: Any = None, form_body: dict | None = None
    ) -> Any:
        """Issue one authenticated request. Returns parsed JSON. Raises ToolError on failure.

        json_body and form_body are mutually exclusive - form_body sends
        application/x-www-form-urlencoded (FastAPI's Form(...) parses this
        identically to multipart/form-data for non-file fields), used for
        endpoints whose OpenAPI schema declares a multipart body instead of
        JSON. See tool_registry.py's ToolEntry.body_encoding.
        """
        token = self._tokens.get_valid_access_token()
        try:
            resp = self._http.request(
                method,
                path,
                params=_drop_none(params),
                json=json_body if form_body is None else None,
                data=form_body,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as exc:
            raise ToolError(0, f"Could not reach BFP backend at {self._base_url}: {exc}") from exc

        if resp.status_code >= 500:
            raise ToolError(resp.status_code, _GENERIC_SERVER_ERROR)

        if resp.status_code >= 400:
            if resp.status_code in _PASSTHROUGH_STATUSES:
                raise ToolError(resp.status_code, _extract_detail(resp))
            # Any other 4xx we didn't anticipate: still safe to pass through -
            # FastAPI validation/HTTPException bodies are always {"detail": ...},
            # never a stack trace, for anything below 500.
            raise ToolError(resp.status_code, _extract_detail(resp))

        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()


def _extract_detail(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("detail", resp.text))
    except ValueError:
        return resp.text


def _drop_none(params: dict | None) -> dict | None:
    if params is None:
        return None
    return {k: v for k, v in params.items() if v is not None}
