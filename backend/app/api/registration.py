"""
POST /api/registration

Ingest an AI-generated artifact:
  1. Read the uploaded file into memory.
  2. Compute SHA-256 hash.
  3. Extract a visual/neural embedding (ResNet/CLIP).
  4. Anchor the record to the provenance ledger (PostgreSQL + pgvector).
  5. Optionally attach a C2PA provenance manifest.

Returns the assigned ledger ID and SHA-256 hash.
"""
import hashlib
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.inference import compute_embedding
from app.core.crypto import compute_salted_hash
from app.core.c2pa_engine import read_c2pa_manifest
from app.database.repository import insert_artifact

router = APIRouter(tags=["registration"])


class RegistrationResponse(BaseModel):
    id: str
    hash: str
    message: str = "Artifact anchored to provenance ledger."


@router.post("/registration", response_model=RegistrationResponse)
async def register_artifact(
    file: UploadFile = File(...),
    model: Optional[str] = Form(default="Unknown"),
    version: Optional[str] = Form(default="1.0"),
    action: Optional[str] = Form(default="GENERATED"),
):
    """
    Register an AI-generated artifact on the provenance ledger.
    Computes SHA-256, visual embedding, and optionally reads C2PA manifest.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file received.")

    # ── Cryptographic hash ────────────────────────────────────────────────────
    sha256 = hashlib.sha256(raw).hexdigest()

    # ── Neural embedding ──────────────────────────────────────────────────────
    embedding = compute_embedding(raw, file.content_type or "")

    # ── Privacy-preserving salted commitment ──────────────────────────────────
    salted = compute_salted_hash(sha256, model or "Unknown")

    # ── C2PA manifest (if embedded in file) ───────────────────────────────────
    c2pa_info = read_c2pa_manifest(raw, file.filename or "")

    # ── Persist to database ───────────────────────────────────────────────────
    record_id = await insert_artifact(
        sha256=sha256,
        filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        model=model or "Unknown",
        version=version or "1.0",
        action=action or "GENERATED",
        embedding=embedding,
        salted_hash=salted,
        c2pa_info=c2pa_info,
    )

    return RegistrationResponse(id=record_id, hash=sha256)
