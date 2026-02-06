"""PaceTrail API - FastAPI application."""
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import configure_logging, request_id_var
from app.api.routers import (
    auth,
    users,
    activities,
    follows,
    likes,
    comments,
    notifications,
    athletes,
    ranks,
    segments,
)

configure_logging()

app = FastAPI(
    title=settings.app_name,
    description="Strava-like activity tracking and social feed API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)


app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(users.router, prefix=settings.api_v1_prefix)
app.include_router(activities.router, prefix=settings.api_v1_prefix)
app.include_router(follows.router, prefix=settings.api_v1_prefix)
app.include_router(likes.router, prefix=settings.api_v1_prefix)
app.include_router(comments.router, prefix=settings.api_v1_prefix)
app.include_router(notifications.router, prefix=settings.api_v1_prefix)
app.include_router(athletes.router, prefix=settings.api_v1_prefix)
app.include_router(ranks.router, prefix=settings.api_v1_prefix)
app.include_router(segments.router, prefix=settings.api_v1_prefix)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@app.get("/")
async def root() -> dict:
    return {"message": "PaceTrail API", "docs": "/docs"}
