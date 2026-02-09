from fastapi import APIRouter

from app.api.v1.endpoints import (
    analysis,
    auth,
    brands,
    campaign_queries,
    campaigns,
    company_profiles,
    comparisons,
    dashboard,
    gallery,
    generated_queries,
    llm,
    operations,
    pipeline,
    projects,
    queries,
    users,
    workspaces,
)

api_router = APIRouter()

# Include all routers
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(workspaces.router)
api_router.include_router(brands.router)
api_router.include_router(queries.router)
api_router.include_router(analysis.router)
api_router.include_router(company_profiles.router)
api_router.include_router(generated_queries.router)
api_router.include_router(llm.router)
api_router.include_router(pipeline.router)
api_router.include_router(campaigns.router)
api_router.include_router(campaign_queries.router)
api_router.include_router(gallery.router)
api_router.include_router(comparisons.router)
api_router.include_router(operations.router)
api_router.include_router(dashboard.router)


@api_router.get("/")
async def root():
    return {"message": "GEO Sensor API v1"}
