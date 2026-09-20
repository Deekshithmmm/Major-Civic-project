import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    auth,
    module1_violations,
    module2_corruption,
    module3_infra,
    module4_emergency,
    public,
)
from app.services.storage import ensure_buckets

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Civic Accountability Platform API",
    description=(
        "All four modules are implemented. Module 1 has no YOLOv8/ANPR pipeline behind it, so "
        "cases arrive from citizen uploads or seed data. Module 4 evidence is reachable only by "
        "an investigating officer supplying a case or FIR number, and any offence involving a "
        "minor is refused outright - see docs/spec-summary.md."
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
app.include_router(module4_emergency.router)
app.include_router(public.router)


@app.on_event("startup")
def on_startup() -> None:
    ensure_buckets()


@app.get("/health")
def health():
    return {"status": "ok"}
