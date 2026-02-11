"""Pipeline endpoints package."""
from fastapi import APIRouter

from .categories import router as categories_router
from .jobs import router as jobs_router
from .query_sets import router as query_sets_router
from .responses import router as responses_router
from .schedules import router as schedules_router
from .stats import router as stats_router

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
router.include_router(jobs_router)
router.include_router(query_sets_router)
router.include_router(categories_router)
router.include_router(responses_router)
router.include_router(stats_router)
router.include_router(schedules_router)
