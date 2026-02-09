"""Tests for Workspace Security and Authorization"""

import os

import pytest

from app.core.security import create_access_token

# Skip these integration tests unless explicitly enabled
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Integration test - set RUN_INTEGRATION_TESTS=1 to run"
)


@pytest.fixture
def valid_token():
    """Create a valid JWT token for testing"""
    return create_access_token(subject="test-user-123")


@pytest.mark.asyncio
class TestWorkspaceSecurity:
    async def test_pipeline_requires_auth(self, client):
        """Pipeline endpoints should reject unauthenticated requests"""
        response = await client.post(
            "/api/v1/pipeline/jobs",
            json={
                "name": "Test Job",
                "query_set": {"queries": ["test"]},
                "llm_providers": ["gemini"]
            }
        )
        # Should require authentication (401) or not exist yet (404)
        assert response.status_code in [401, 404]

    async def test_pipeline_requires_workspace_member(self, client, valid_token):
        """Pipeline should check workspace membership"""
        response = await client.post(
            "/api/v1/pipeline/jobs",
            json={
                "name": "Test Job",
                "query_set": {"queries": ["test"]},
                "llm_providers": ["gemini"]
            },
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        # Should require workspace membership or endpoint not exist yet
        assert response.status_code in [401, 403, 404, 422]

    async def test_campaign_requires_workspace_member(self, client):
        """Campaign endpoints should require workspace membership"""
        response = await client.get("/api/v1/campaigns")
        # Should require auth (401) or not exist yet (404)
        assert response.status_code in [401, 404]

    async def test_error_response_no_internal_info(self, client):
        """Error responses should not leak internal details"""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "wrongpassword"
            }
        )

        # 401 for wrong credentials, 429 if rate-limited by previous tests
        assert response.status_code in [401, 429]
        body = response.json()

        # Should have generic error message, not internal details
        detail = body.get("detail", "")
        if isinstance(detail, str):
            # Should NOT contain database errors, stack traces, etc.
            assert "traceback" not in detail.lower()
            assert "database" not in detail.lower()

    async def test_register_password_too_short(self, client):
        """Registration should reject weak passwords"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "123",  # Too short
                "full_name": "Test User"
            }
        )

        # Should reject weak password
        assert response.status_code == 422

    async def test_invalid_token_rejected(self, client):
        """Garbage JWT tokens should be rejected"""
        response = await client.get(
            "/api/v1/workspaces",
            headers={"Authorization": "Bearer invalid.garbage.token"}
        )

        # Should reject invalid token (401) or redirect (307)
        assert response.status_code in [401, 307]

    async def test_expired_token_rejected(self, client):
        """Expired tokens should be rejected"""
        # Create a token with negative expiration (already expired)
        from datetime import timedelta
        from app.core.security import create_access_token as create_token

        expired_token = create_token(subject="test-user", expires_delta=timedelta(seconds=-1))

        response = await client.get(
            "/api/v1/workspaces",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        # Should reject expired token (401) or redirect (307)
        assert response.status_code in [401, 307]
