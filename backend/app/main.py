import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, module1_violations, module2_corruption, module3_infra, public
from app.services.storage import ensure_buckets

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Civic Accountability Platform API",
    description=(
        "Module 3 (civic infrastructure reporting) is fully implemented. Modules 1 and 2 have "
        "working upload/review/routing flows but no CV pipeline or moderation frontend yet. "
        "Module 4 is schema-only and intentionally has no routes - see docs/spec-summary.md."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(module3_infra.router)
app.include_router(module1_violations.router)
app.include_router(module2_corruption.router)
app.include_router(public.router)


@app.on_event("startup")
def on_startup() -> None:
    ensure_buckets()


@app.get("/health")
def health():
    return {"status": "ok"}
