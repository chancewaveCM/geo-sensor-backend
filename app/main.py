import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, set_correlation_id

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


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Correlation-ID"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}
