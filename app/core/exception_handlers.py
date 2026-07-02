"""Application-level exception handlers."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.utils.logger import get_logger

logger = get_logger(__name__)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Hide internal exception details from API clients."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
