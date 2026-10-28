"""FastAPI application entry point."""

import logging
import re
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.institutions import router as institutions_router
from app.api.fdrs import router as fdrs_router
from app.api.dashboard_reports import router as dashboard_reports_router
from app.api.monitoring import router as monitoring_router
from app.api.documents import router as documents_router
from app.core.config import app_environment, frontend_origin, validate_security_settings, validate_storage_root
from app.services.scheduler import optional_scheduler


@asynccontextmanager
async def lifespan(application: FastAPI):
    validate_storage_root()
    if app_environment() != "test":
        from app.db.session import make_session_factory
        from app.services.document_processing import stale_processing_count
        try:
            with make_session_factory()() as session:
                logging.getLogger("fdr_guardian.documents").info("stale_document_count", extra={"count": stale_processing_count(session)})
        except Exception as exc:
            logging.getLogger("fdr_guardian.documents").warning("stale_document_count_unavailable", extra={"error_type": type(exc).__name__})
    scheduler = optional_scheduler()
    application.state.monitoring_scheduler = scheduler
    if scheduler is not None:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=True)

def create_app() -> FastAPI:
    validate_security_settings()
    production = app_environment() == "production"
    application = FastAPI(
        title="FDR Guardian API",
        description="Foundation API for security deposit and FDR lifecycle management.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[frontend_origin()],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    application.include_router(router)
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(admin_router, prefix="/api/v1")
    application.include_router(institutions_router, prefix="/api/v1")
    application.include_router(fdrs_router, prefix="/api/v1")
    application.include_router(dashboard_reports_router, prefix="/api/v1")
    application.include_router(monitoring_router, prefix="/api/v1")
    application.include_router(documents_router, prefix="/api/v1")
    return application


app = create_app()


@app.middleware("http")
async def request_id_middleware(request, call_next):
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming if re.fullmatch(r"[A-Za-z0-9._:-]{1,120}", incoming) else str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
