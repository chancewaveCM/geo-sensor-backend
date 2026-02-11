"""Unit tests for RFC 7807 error handlers."""

from unittest.mock import MagicMock

import pytest

from app.core.error_handlers import problem_detail_handler
from app.core.exceptions import (
    ConflictError,
    InternalError,
    LLMProviderError,
    NotFoundError,
    PermissionDeniedError,
    ProblemDetail,
    RateLimitError,
    ValidationError,
)


class TestProblemDetail:
    """Tests for ProblemDetail base class."""

    def test_creates_correct_status(self) -> None:
        """Test that ProblemDetail sets status correctly."""
        exc = ProblemDetail(
            status=404,
            title="Not Found",
            detail="Resource not found",
            error_code="TEST-001",
        )

        assert exc.status == 404
        assert exc.title == "Not Found"
        assert exc.detail == "Resource not found"
        assert exc.error_code == "TEST-001"

    def test_optional_instance(self) -> None:
        """Test that instance is optional."""
        exc = ProblemDetail(
            status=500,
            title="Error",
            detail="Something broke",
            error_code="TEST-002",
        )

        assert exc.instance is None

    def test_optional_extra(self) -> None:
        """Test that extra dict is optional."""
        exc = ProblemDetail(
            status=500,
            title="Error",
            detail="Something broke",
            error_code="TEST-003",
        )

        assert exc.extra == {}

    def test_extra_data(self) -> None:
        """Test that extra data is stored correctly."""
        exc = ProblemDetail(
            status=422,
            title="Validation Error",
            detail="Invalid input",
            error_code="TEST-004",
            extra={"field": "email", "constraint": "format"},
        )

        assert exc.extra == {"field": "email", "constraint": "format"}


class TestNotFoundError:
    """Tests for NotFoundError."""

    def test_sets_status_404(self) -> None:
        """Test that NotFoundError sets status=404."""
        exc = NotFoundError(resource="Campaign", resource_id=123)

        assert exc.status == 404

    def test_correct_error_code(self) -> None:
        """Test that error_code is GEO-1001."""
        exc = NotFoundError(resource="Campaign", resource_id=123)

        assert exc.error_code == "GEO-1001"

    def test_detail_message_format(self) -> None:
        """Test that detail message is formatted correctly."""
        exc = NotFoundError(resource="Campaign", resource_id=123)

        assert "Campaign" in exc.detail
        assert "123" in exc.detail
        assert "not found" in exc.detail


class TestPermissionDeniedError:
    """Tests for PermissionDeniedError."""

    def test_sets_status_403(self) -> None:
        """Test that PermissionDeniedError sets status=403."""
        exc = PermissionDeniedError()

        assert exc.status == 403

    def test_correct_error_code(self) -> None:
        """Test that error_code is GEO-1002."""
        exc = PermissionDeniedError()

        assert exc.error_code == "GEO-1002"

    def test_default_detail(self) -> None:
        """Test default detail message."""
        exc = PermissionDeniedError()

        assert exc.detail == "You don't have permission"

    def test_custom_detail(self) -> None:
        """Test custom detail message."""
        exc = PermissionDeniedError(detail="Admin access required")

        assert exc.detail == "Admin access required"


class TestValidationError:
    """Tests for ValidationError."""

    def test_sets_status_422(self) -> None:
        """Test that ValidationError sets status=422."""
        exc = ValidationError(detail="Invalid email format")

        assert exc.status == 422

    def test_correct_error_code(self) -> None:
        """Test that error_code is GEO-1003."""
        exc = ValidationError(detail="Invalid input")

        assert exc.error_code == "GEO-1003"


class TestLLMProviderError:
    """Tests for LLMProviderError."""

    def test_sets_status_502(self) -> None:
        """Test that LLMProviderError sets status=502."""
        exc = LLMProviderError(provider="gemini", detail="API timeout")

        assert exc.status == 502

    def test_correct_error_code(self) -> None:
        """Test that error_code is GEO-2001."""
        exc = LLMProviderError(provider="gemini", detail="API timeout")

        assert exc.error_code == "GEO-2001"

    def test_title_includes_provider(self) -> None:
        """Test that title includes provider name."""
        exc = LLMProviderError(provider="openai", detail="Rate limit exceeded")

        assert "openai" in exc.title


@pytest.mark.asyncio
class TestProblemDetailHandler:
    """Tests for problem_detail_handler."""

    async def test_returns_rfc7807_json_format(self) -> None:
        """Test that handler returns RFC 7807 compliant JSON."""
        exc = NotFoundError(resource="Campaign", resource_id=42)
        request = MagicMock()
        request.url = "http://test/api/campaigns/42"

        response = await problem_detail_handler(request, exc)

        assert response.status_code == 404
        assert response.headers["Content-Type"] == "application/problem+json"

        body = response.body.decode()
        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "detail" in body
        assert "error_code" in body
        assert "instance" in body

    async def test_includes_error_code_in_type_url(self) -> None:
        """Test that type URL includes error code."""
        exc = ValidationError(detail="Bad input")
        request = MagicMock()
        request.url = "http://test/api/endpoint"

        response = await problem_detail_handler(request, exc)
        body_dict = eval(response.body.decode())  # Simple parse for test

        assert "GEO-1003" in body_dict["type"]

    async def test_includes_request_url_as_instance(self) -> None:
        """Test that instance defaults to request URL."""
        exc = PermissionDeniedError()
        request = MagicMock()
        request.url = "http://test/api/restricted"

        response = await problem_detail_handler(request, exc)
        body_dict = eval(response.body.decode())

        assert body_dict["instance"] == str(request.url)

    async def test_respects_custom_instance(self) -> None:
        """Test that custom instance is used if provided."""
        exc = ProblemDetail(
            status=400,
            title="Error",
            detail="Details",
            error_code="TEST-001",
            instance="/custom/path",
        )
        request = MagicMock()
        request.url = "http://test/api/endpoint"

        response = await problem_detail_handler(request, exc)
        body_dict = eval(response.body.decode())

        assert body_dict["instance"] == "/custom/path"

    async def test_includes_extra_fields(self) -> None:
        """Test that extra fields are included in response."""
        exc = ProblemDetail(
            status=422,
            title="Validation Failed",
            detail="Invalid data",
            error_code="TEST-002",
            extra={"field": "email", "reason": "Invalid format"},
        )
        request = MagicMock()
        request.url = "http://test/api/endpoint"

        response = await problem_detail_handler(request, exc)
        body_dict = eval(response.body.decode())

        assert body_dict["field"] == "email"
        assert body_dict["reason"] == "Invalid format"


class TestConflictError:
    """Tests for ConflictError."""

    def test_sets_status_409(self) -> None:
        """Test that ConflictError sets status=409."""
        exc = ConflictError(detail="Resource already exists")

        assert exc.status == 409
        assert exc.error_code == "GEO-1004"


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_sets_status_429(self) -> None:
        """Test that RateLimitError sets status=429."""
        exc = RateLimitError()

        assert exc.status == 429
        assert exc.error_code == "GEO-1005"
        assert "Too many requests" in exc.detail


class TestInternalError:
    """Tests for InternalError."""

    def test_sets_status_500(self) -> None:
        """Test that InternalError sets status=500."""
        exc = InternalError()

        assert exc.status == 500
        assert exc.error_code == "GEO-1006"
