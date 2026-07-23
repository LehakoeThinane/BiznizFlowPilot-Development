"""Application-level exception handlers."""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.utils.logger import get_logger

logger = get_logger(__name__)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Hide internal exception details from API clients."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """slowapi's own default handler responds with {"error": ...}, not
    {"detail": ...} - every other error path in this API (and the frontend's
    extractErrorMessage, which only looks for "detail") uses "detail", so a
    rate-limited request fell through to a generic "Request failed" instead
    of telling the user they've been rate-limited. Keep the response shape
    consistent with the rest of the API."""
    response = JSONResponse(
        status_code=429,
        content={"detail": "Too many attempts - please wait a while and try again."},
    )
    return request.app.state.limiter._inject_headers(response, request.state.view_rate_limit)
