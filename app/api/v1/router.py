from fastapi import APIRouter

from app.api.v1.endpoints import analysis, auth, brands, projects, queries

api_router = APIRouter()

# Include all routers
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(brands.router)
api_router.include_router(queries.router)
api_router.include_router(analysis.router)


@api_router.get("/")
async def root():
    return {"message": "GEO Sensor API v1"}
