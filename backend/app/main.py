import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import (
    auth,
    module1_violations,
    module2_corruption,
    module3_infra,
    module4_emergency,
    public,
)
from app.security import security_headers_middleware
from app.services.storage import ensure_buckets

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_buckets()
    yield


app = FastAPI(
    title="Civic Accountability Platform API",
    description=(
        "All four modules are implemented. Module 1 has no YOLOv8/ANPR pipeline behind it, so "
        "cases arrive from citizen uploads or seed data. Module 4 evidence is reachable only by "
        "an investigating officer supplying a case or FIR number, and any offence involving a "
        "minor is refused outright - see docs/spec-summary.md."
    ),
    version="0.1.0",
    lifespan=lifespan,
    # The schema names every route, including the officer-only ones, and is an inventory for
    # anyone probing the deployment. Useful locally, not something to publish.
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
)

app.middleware("http")(security_headers_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Id"],
)

app.include_router(auth.router)
app.include_router(module3_infra.router)
app.include_router(module1_violations.router)
app.include_router(module2_corruption.router)
app.include_router(module4_emergency.router)
app.include_router(public.router)


@app.get("/health")
def health():
    return {"status": "ok"}
