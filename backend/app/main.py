from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.api.router import api_router
from app.api.routes import health
from app.config.settings import get_settings
from app.logging.setup import configure_logging
from app.middleware.exception_handler import register_exception_handlers
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware

settings = get_settings()
configure_logging(settings.debug)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A production-grade distributed job scheduler — atomic job claiming, "
    "retries with backoff, dead-letter queues, and realtime observability.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)

register_exception_handlers(app)
app.include_router(health.router)
app.include_router(api_router, prefix="/api/v1")


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
