"""RFC 7807 Problem Details for HTTP APIs."""


class ProblemDetail(Exception):
    """RFC 7807 Problem Details for HTTP APIs"""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str,
        error_code: str,  # e.g., "GEO-1001"
        instance: str | None = None,
        extra: dict | None = None,
    ):
        self.status = status
        self.title = title
        self.detail = detail
        self.error_code = error_code
        self.instance = instance
        self.extra = extra or {}
        super().__init__(detail)


# Predefined exceptions
class NotFoundError(ProblemDetail):
    """Resource not found error."""

    def __init__(self, resource: str, resource_id: int | str, **kwargs):
        super().__init__(
            status=404,
            title=f"{resource} Not Found",
            detail=f"{resource} with id '{resource_id}' was not found",
            error_code="GEO-1001",
            **kwargs,
        )


class PermissionDeniedError(ProblemDetail):
    """Permission denied error."""

    def __init__(self, detail: str = "You don't have permission", **kwargs):
        super().__init__(
            status=403,
            title="Permission Denied",
            detail=detail,
            error_code="GEO-1002",
            **kwargs,
        )


class ValidationError(ProblemDetail):
    """Validation error."""

    def __init__(self, detail: str, **kwargs):
        super().__init__(
            status=422,
            title="Validation Error",
            detail=detail,
            error_code="GEO-1003",
            **kwargs,
        )


class ConflictError(ProblemDetail):
    """Resource conflict error."""

    def __init__(self, detail: str, **kwargs):
        super().__init__(
            status=409,
            title="Conflict",
            detail=detail,
            error_code="GEO-1004",
            **kwargs,
        )


class RateLimitError(ProblemDetail):
    """Rate limit exceeded error."""

    def __init__(self, **kwargs):
        super().__init__(
            status=429,
            title="Rate Limit Exceeded",
            detail="Too many requests",
            error_code="GEO-1005",
            **kwargs,
        )


class InternalError(ProblemDetail):
    """Internal server error."""

    def __init__(self, detail: str = "An internal error occurred", **kwargs):
        super().__init__(
            status=500,
            title="Internal Server Error",
            detail=detail,
            error_code="GEO-1006",
            **kwargs,
        )


class LLMProviderError(ProblemDetail):
    """LLM provider error."""

    def __init__(self, provider: str, detail: str, **kwargs):
        super().__init__(
            status=502,
            title=f"LLM Provider Error ({provider})",
            detail=detail,
            error_code="GEO-2001",
            **kwargs,
        )


class PipelineError(ProblemDetail):
    """Pipeline execution error."""

    def __init__(self, detail: str, **kwargs):
        super().__init__(
            status=500,
            title="Pipeline Execution Error",
            detail=detail,
            error_code="GEO-2002",
            **kwargs,
        )
