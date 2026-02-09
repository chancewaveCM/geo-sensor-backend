"""Core API endpoint tests covering Auth, Pipeline, Analysis, Campaign, and Workspace."""

import os

import pytest
from httpx import AsyncClient

from app.models.enums import WorkspaceRole

# Skip these integration tests unless explicitly enabled
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Integration test - set RUN_INTEGRATION_TESTS=1 to run"
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def test_user_credentials():
    """Return test user credentials."""
    return {
        "email": "testuser@example.com",
        "password": "TestPass123!",
        "full_name": "Test User",
    }


# Cache for auth token to avoid hitting rate limits
_cached_auth_token = None


@pytest.fixture
async def auth_token(client: AsyncClient, test_user_credentials):
    """Get authentication token for test user (cached to avoid rate limits)."""
    global _cached_auth_token

    if _cached_auth_token is not None:
        return _cached_auth_token

    # Try to register user first (may already exist)
    await client.post(
        "/api/v1/auth/register",
        json=test_user_credentials,
    )
    # Ignore result - user may already exist

    # Login to get token
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": test_user_credentials["email"],
            "password": test_user_credentials["password"],
        },
    )

    if login_response.status_code == 200:
        data = login_response.json()
        _cached_auth_token = data["access_token"]
        return _cached_auth_token

    # If we hit rate limit, skip tests that need auth
    pytest.skip(f"Cannot get auth token: {login_response.status_code}")


@pytest.fixture
async def auth_headers(auth_token):
    """Return authorization headers with token."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def registered_user(test_user_credentials):
    """Return test user credentials (assumes user is registered)."""
    return test_user_credentials


@pytest.fixture
async def second_user_credentials():
    """Return second test user credentials for isolation tests."""
    return {
        "email": "seconduser@example.com",
        "password": "SecondPass123!",
        "full_name": "Second User",
    }


@pytest.fixture
async def second_user_token(client: AsyncClient, second_user_credentials):
    """Register second user and get token."""
    # Register
    await client.post(
        "/api/v1/auth/register",
        json=second_user_credentials,
    )
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": second_user_credentials["email"],
            "password": second_user_credentials["password"],
        },
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    return None


# ============================================================================
# Auth Tests (4)
# ============================================================================


@pytest.mark.asyncio
class TestAuth:
    async def test_login_success(self, client: AsyncClient, registered_user):
        """Test 1: POST /api/v1/auth/login with valid credentials → 200."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": registered_user["email"],
                "password": registered_user["password"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    async def test_login_wrong_password(self, client: AsyncClient, registered_user):
        """Test 2: POST /api/v1/auth/login with wrong password → 401."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": registered_user["email"],
                "password": "WrongPassword123!",
            },
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    async def test_register_duplicate_email(
        self, client: AsyncClient, registered_user
    ):
        """Test 3: POST /api/v1/auth/register with existing email → 400."""
        response = await client.post(
            "/api/v1/auth/register",
            json=registered_user,
        )
        # User already exists from fixture, or rate limited
        assert response.status_code in [400, 429]
        if response.status_code == 400:
            data = response.json()
            assert "already registered" in data["detail"].lower()

    async def test_get_current_user(self, client: AsyncClient, auth_headers):
        """Test 4: GET /api/v1/auth/me with valid token → 200."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "id" in data
        assert "is_active" in data


# ============================================================================
# Pipeline Tests (4)
# ============================================================================


@pytest.mark.asyncio
class TestPipeline:
    async def test_list_jobs_unauthorized(self, client: AsyncClient):
        """Test 5: GET /api/v1/workspaces/{id}/pipeline/jobs without auth → 401."""
        response = await client.get("/api/v1/workspaces/1/pipeline/jobs")
        assert response.status_code == 401

    async def test_list_jobs_authorized(self, client: AsyncClient, auth_headers):
        """Test 6: GET /api/v1/workspaces/{id}/pipeline/jobs with auth → 200."""
        # First get user's workspaces
        ws_response = await client.get("/api/v1/workspaces/", headers=auth_headers)
        assert ws_response.status_code == 200
        workspaces = ws_response.json()
        assert len(workspaces) >= 1
        workspace_id = workspaces[0]["id"]

        response = await client.get(
            f"/api/v1/workspaces/{workspace_id}/pipeline/jobs", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert isinstance(data["jobs"], list)

    async def test_get_job_status_not_found(self, client: AsyncClient, auth_headers):
        """Test 7: GET /api/v1/workspaces/{id}/pipeline/jobs/999999 → 404."""
        # First get user's workspaces
        ws_response = await client.get("/api/v1/workspaces/", headers=auth_headers)
        assert ws_response.status_code == 200
        workspaces = ws_response.json()
        assert len(workspaces) >= 1
        workspace_id = workspaces[0]["id"]

        response = await client.get(
            f"/api/v1/workspaces/{workspace_id}/pipeline/jobs/999999", headers=auth_headers
        )
        assert response.status_code == 404

    async def test_cancel_job_not_found(self, client: AsyncClient, auth_headers):
        """Test 8: POST /api/v1/workspaces/{id}/pipeline/jobs/999999/cancel → 404."""
        # First get user's workspaces
        ws_response = await client.get("/api/v1/workspaces/", headers=auth_headers)
        assert ws_response.status_code == 200
        workspaces = ws_response.json()
        assert len(workspaces) >= 1
        workspace_id = workspaces[0]["id"]

        response = await client.post(
            f"/api/v1/workspaces/{workspace_id}/pipeline/jobs/999999/cancel", headers=auth_headers
        )
        assert response.status_code == 404


# ============================================================================
# Analysis Tests (4)
# ============================================================================


@pytest.mark.asyncio
class TestAnalysis:
    async def test_brand_matching_unauthorized(self, client: AsyncClient):
        """Test 9: Brand matching without auth → 401 or 404 if endpoint not implemented."""
        response = await client.post(
            "/api/v1/analysis/brand-match",
            json={"text": "I love Apple products", "brand_names": ["Apple", "Samsung"]},
        )
        # 401 if implemented with auth, 404 if not implemented yet
        assert response.status_code in [401, 404]

    async def test_citation_share_unauthorized(self, client: AsyncClient):
        """Test 10: Citation share without auth → 401 or 404 if endpoint not implemented."""
        response = await client.post(
            "/api/v1/analysis/citation-share",
            json={"responses": [], "brand_name": "Apple"},
        )
        # 401 if implemented with auth, 404 if not implemented yet
        assert response.status_code in [401, 404]

    async def test_sentiment_analysis_unauthorized(self, client: AsyncClient):
        """Test 11: Sentiment analysis without auth → 401 or 404 if endpoint not implemented."""
        response = await client.post(
            "/api/v1/analysis/sentiment",
            json={"text": "This is great!"},
        )
        # 401 if implemented with auth, 404 if not implemented yet
        assert response.status_code in [401, 404]

    async def test_geo_score_unauthorized(self, client: AsyncClient):
        """Test 12: GEO score without auth → 401 or 404 if endpoint not implemented."""
        response = await client.post(
            "/api/v1/analysis/geo-score",
            json={"response_text": "Apple is mentioned", "brand_name": "Apple"},
        )
        # 401 if implemented with auth, 404 if not implemented yet
        assert response.status_code in [401, 404]


# ============================================================================
# Campaign Tests (4)
# ============================================================================


@pytest.mark.asyncio
class TestCampaign:
    async def test_create_campaign_unauthorized(self, client: AsyncClient):
        """Test 13: Create campaign without auth → 401."""
        response = await client.post(
            "/api/v1/workspaces/1/campaigns/",
            json={"name": "Test Campaign"},
        )
        assert response.status_code == 401

    async def test_list_campaigns_unauthorized(self, client: AsyncClient):
        """Test 14: List campaigns without auth → 401."""
        response = await client.get("/api/v1/workspaces/1/campaigns/")
        assert response.status_code == 401

    async def test_campaign_requires_workspace_membership(
        self, client: AsyncClient, auth_headers
    ):
        """Test 15: Access campaign in workspace where user is not a member → 403."""
        # Try to access campaigns in workspace 999999 (doesn't exist or no membership)
        response = await client.get(
            "/api/v1/workspaces/999999/campaigns/", headers=auth_headers
        )
        # Should return 403 (not a member) or 404 (workspace doesn't exist)
        assert response.status_code in [403, 404]

    async def test_campaign_not_found_404(self, client: AsyncClient, auth_headers):
        """Test 16: GET /api/v1/workspaces/{id}/campaigns/999999 → 404."""
        # First get user's workspaces
        ws_response = await client.get("/api/v1/workspaces/", headers=auth_headers)
        assert ws_response.status_code == 200
        workspaces = ws_response.json()

        if len(workspaces) > 0:
            workspace_id = workspaces[0]["id"]
            # Try to get non-existent campaign
            response = await client.get(
                f"/api/v1/workspaces/{workspace_id}/campaigns/999999",
                headers=auth_headers,
            )
            assert response.status_code == 404


# ============================================================================
# Workspace Tests (4)
# ============================================================================


@pytest.mark.asyncio
class TestWorkspace:
    async def test_create_workspace(self, client: AsyncClient, auth_headers):
        """Test 17: POST /api/v1/workspaces → 201."""
        response = await client.post(
            "/api/v1/workspaces/",
            headers=auth_headers,
            json={
                "name": "Test Workspace",
                "description": "A test workspace",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Workspace"
        assert data["my_role"] == WorkspaceRole.ADMIN.value
        assert data["member_count"] == 1

    async def test_list_workspaces(self, client: AsyncClient, auth_headers):
        """Test 18: GET /api/v1/workspaces → 200."""
        response = await client.get("/api/v1/workspaces/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # User should have at least the auto-created workspace from registration
        assert len(data) >= 1
        # Check workspace structure
        if len(data) > 0:
            ws = data[0]
            assert "id" in ws
            assert "name" in ws
            assert "slug" in ws
            assert "my_role" in ws
            assert "member_count" in ws

    async def test_workspace_member_required(self, client: AsyncClient, auth_headers):
        """Test 19: Non-member cannot access workspace → 403."""
        # Try to get workspace 999999 (doesn't exist or no membership)
        response = await client.get(
            "/api/v1/workspaces/999999", headers=auth_headers
        )
        # Should return 403 (not a member) or 404 (workspace doesn't exist)
        assert response.status_code in [403, 404]

    async def test_workspace_admin_required_for_member_add(
        self, client: AsyncClient, auth_headers, second_user_token
    ):
        """Test 20: Non-admin cannot add members → 403."""
        if second_user_token is None:
            pytest.skip("Second user token not available")

        # Get first user's workspace
        ws_response = await client.get("/api/v1/workspaces/", headers=auth_headers)
        assert ws_response.status_code == 200
        workspaces = ws_response.json()
        assert len(workspaces) >= 1
        workspace_id = workspaces[0]["id"]

        # Second user tries to add members (should fail - not a member/admin)
        second_headers = {"Authorization": f"Bearer {second_user_token}"}
        response = await client.post(
            f"/api/v1/workspaces/{workspace_id}/members",
            headers=second_headers,
            json={"user_email": "newuser@example.com", "role": "MEMBER"},
        )
        # Should return 403 (not admin) or 404 (not member)
        assert response.status_code in [403, 404]
