import asyncio
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import update
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, set_correlation_id
from app.db.session import async_session_maker
from app.models.enums import PipelineStatus
from app.models.pipeline_job import PipelineJob
from app.services.campaign.scheduler import get_scheduler
from app.services.scheduler.pipeline_scheduler import get_pipeline_scheduler

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = set_correlation_id()
        start_time = time.time()

        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                f"{request.method} {request.url.path} "
                f"status={response.status_code} "
                f"duration={process_time:.3f}s"
            )
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Process-Time"] = str(process_time)
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"{request.method} {request.url.path} "
                f"error={type(e).__name__}: {e} "
                f"duration={process_time:.3f}s"
            )
            raise


STUCK_STATUSES = [
    PipelineStatus.PENDING,
    PipelineStatus.GENERATING_CATEGORIES,
    PipelineStatus.EXPANDING_QUERIES,
    PipelineStatus.EXECUTING_QUERIES,
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Mark stuck pipeline jobs as FAILED on startup and start scheduler."""
    async with async_session_maker() as db:
        result = await db.execute(
            update(PipelineJob)
            .where(PipelineJob.status.in_(STUCK_STATUSES))
            .values(
                status=PipelineStatus.FAILED,
                error_message="Server restarted while job was running",
                completed_at=datetime.now(tz=UTC),
            )
            .returning(PipelineJob.id)
        )
        failed_ids = [row[0] for row in result.fetchall()]
        if failed_ids:
            await db.commit()
            logger.info(f"Marked {len(failed_ids)} stuck jobs as FAILED: {failed_ids}")
        else:
            logger.info("No stuck pipeline jobs found on startup")

    # Start campaign scheduler in background
    scheduler = get_scheduler(poll_interval_seconds=300)  # 5 min interval
    scheduler_task = asyncio.create_task(scheduler.start())
    logger.info("Campaign scheduler started")

    # Start pipeline scheduler in background
    pipeline_scheduler = get_pipeline_scheduler(poll_interval_seconds=300)  # 5 min interval
    pipeline_scheduler_task = asyncio.create_task(pipeline_scheduler.start())
    logger.info("Pipeline scheduler started")

    yield

    # Shutdown pipeline scheduler
    pipeline_scheduler.stop()
    pipeline_scheduler_task.cancel()
    try:
        await pipeline_scheduler_task
    except asyncio.CancelledError:
        pass
    logger.info("Pipeline scheduler stopped")

    # Shutdown campaign scheduler
    scheduler.stop()
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    logger.info("Campaign scheduler stopped")


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Correlation-ID"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}
