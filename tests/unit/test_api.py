"""API endpoint tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
class TestProjectEndpoints:
    async def test_list_projects_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/projects/")
        assert response.status_code == 401

    async def test_create_project_unauthorized(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/projects/",
            json={"name": "Test Project"}
        )
        assert response.status_code == 401

    async def test_get_project_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/projects/1")
        assert response.status_code == 401

    async def test_update_project_unauthorized(self, client: AsyncClient):
        response = await client.put(
            "/api/v1/projects/1",
            json={"name": "Updated Project"}
        )
        assert response.status_code == 401

    async def test_delete_project_unauthorized(self, client: AsyncClient):
        response = await client.delete("/api/v1/projects/1")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestBrandEndpoints:
    async def test_list_brands_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/brands/?project_id=1")
        assert response.status_code == 401

    async def test_create_brand_unauthorized(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/brands/",
            json={"name": "Test Brand", "project_id": 1}
        )
        assert response.status_code == 401

    async def test_get_brand_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/brands/1")
        assert response.status_code == 401

    async def test_update_brand_unauthorized(self, client: AsyncClient):
        response = await client.put(
            "/api/v1/brands/1",
            json={"name": "Updated Brand"}
        )
        assert response.status_code == 401

    async def test_delete_brand_unauthorized(self, client: AsyncClient):
        response = await client.delete("/api/v1/brands/1")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestQueryEndpoints:
    async def test_list_queries_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/queries/?project_id=1")
        assert response.status_code == 401

    async def test_create_query_unauthorized(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/queries/",
            json={"text": "Test query", "project_id": 1}
        )
        assert response.status_code == 401

    async def test_get_query_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/queries/1")
        assert response.status_code == 401

    async def test_delete_query_unauthorized(self, client: AsyncClient):
        response = await client.delete("/api/v1/queries/1")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestAnalysisEndpoints:
    async def test_run_analysis_unauthorized(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/analysis/run",
            json={"query_id": 1}
        )
        assert response.status_code == 401

    async def test_get_analysis_results_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/analysis/results/1")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestAPIRoot:
    async def test_api_root(self, client: AsyncClient):
        response = await client.get("/api/v1/")
        assert response.status_code == 200
        assert response.json() == {"message": "GEO Sensor API v1"}
