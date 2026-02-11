"""Campaign endpoints package."""
from fastapi import APIRouter

from .analytics import router as analytics_router
from .base import router as base_router
from .competitive import router as competitive_router
from .timeseries import router as timeseries_router

router = APIRouter(prefix="/workspaces/{workspace_id}/campaigns", tags=["campaigns"])
router.include_router(base_router)
router.include_router(analytics_router)
router.include_router(timeseries_router)
router.include_router(competitive_router)
