"""FastAPI application entry point."""

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
from app.core.config import frontend_origin, validate_security_settings
from app.services.scheduler import optional_scheduler


@asynccontextmanager
async def lifespan(application: FastAPI):
    scheduler = optional_scheduler()
    application.state.monitoring_scheduler = scheduler
    if scheduler is not None:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=True)

validate_security_settings()

app = FastAPI(
    title="FDR Guardian API",
    description="Foundation API for security deposit and FDR lifecycle management.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.include_router(router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(institutions_router, prefix="/api/v1")
app.include_router(fdrs_router, prefix="/api/v1")
app.include_router(dashboard_reports_router, prefix="/api/v1")
app.include_router(monitoring_router, prefix="/api/v1")


@app.middleware("http")
async def request_id_middleware(request, call_next):
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming if re.fullmatch(r"[A-Za-z0-9._:-]{1,120}", incoming) else str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
