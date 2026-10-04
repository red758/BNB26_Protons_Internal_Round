"""
ProvLedger — FastAPI Backend Entry Point
Initialises the app, configures CORS, mounts API routers,
and wires up the database on startup.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.registration import router as registration_router
from app.api.verification import router as verification_router
from app.database.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hook."""
    init_db()
    yield


app = FastAPI(
    title="ProvLedger API",
    description="Cryptographic AI Content Provenance — registration and verification engine.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(registration_router, prefix="/api")
app.include_router(verification_router, prefix="/api")


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": "ProvLedger API"}
