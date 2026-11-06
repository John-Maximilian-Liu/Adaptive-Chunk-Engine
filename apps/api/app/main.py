"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.errors import APIError, api_error_handler, unhandled_error_handler
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.services.engine import get_engine

settings = get_settings()
setup_logging(settings.log_json)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = get_engine()
    if not engine.tenants:
        seed = engine.seed_development()
        logger.info("Seeded development data: %s", {k: seed[k] for k in seed if k != "demo_document"})
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Secure headers middleware
@app.middleware("http")
async def secure_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-XSS-Protection"] = "0"
    if hasattr(request.state, "correlation_id"):
        response.headers["X-Correlation-ID"] = request.state.correlation_id
    return response


app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)
app.include_router(v1_router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    return {"service": settings.app_name, "docs": "/docs", "api": settings.api_prefix}
