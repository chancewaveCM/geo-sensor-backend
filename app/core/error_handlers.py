"""Global exception handlers for FastAPI."""

from fastapi import Request
from fastapi.responses import JSONResponse

from .exceptions import ProblemDetail


async def problem_detail_handler(request: Request, exc: ProblemDetail) -> JSONResponse:
    """Handle ProblemDetail exceptions with RFC 7807 format."""
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
