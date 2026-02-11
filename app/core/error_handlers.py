"""Global exception handlers for FastAPI."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from .exceptions import ProblemDetail

logger = logging.getLogger(__name__)


async def problem_detail_handler(request: Request, exc: ProblemDetail) -> JSONResponse:
    """Handle ProblemDetail exceptions with RFC 7807 format."""
    # Log server errors (5xx)
    if exc.status >= 500:
        logger.error(
            f"Server error [{exc.error_code}]: {exc.detail}",
            extra={"path": str(request.url)},
        )

    return JSONResponse(
        status_code=exc.status,
        content={
            "type": f"https://geo-sensor.dev/errors/{exc.error_code}",
            "title": exc.title,
            "status": exc.status,
            "detail": exc.detail,
            "error_code": exc.error_code,
            "instance": exc.instance or str(request.url),
            **exc.extra,
        },
        headers={"Content-Type": "application/problem+json"},
    )
