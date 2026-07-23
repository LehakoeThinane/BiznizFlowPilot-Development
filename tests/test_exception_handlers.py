"""Tests for app-level exception handlers (app/core/exception_handlers.py)."""

from __future__ import annotations

import json

from starlette.requests import Request

from app.core.exception_handlers import rate_limit_exceeded_handler
from app.main import app


async def test_rate_limit_exceeded_response_has_a_detail_field():
    """slowapi's own default handler responds with {"error": ...}, but every
    other error path in this API - and the frontend's shared error parser,
    which only reads "detail" - uses {"detail": ...}. A rate-limited request
    must get the same shape, or it falls through to a generic, unhelpful
    "Request failed" on the frontend instead of a real message."""
    scope = {"type": "http", "method": "POST", "path": "/api/v1/signup/trial", "headers": [], "app": app}
    request = Request(scope)
    request.state.view_rate_limit = None  # no active window to report headers for

    response = await rate_limit_exceeded_handler(request, exc=None)

    assert response.status_code == 429
    body = json.loads(response.body)
    assert "detail" in body
    assert isinstance(body["detail"], str)
    assert body["detail"]
