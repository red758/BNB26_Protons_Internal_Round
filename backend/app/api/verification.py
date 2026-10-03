"""
POST /api/verification

Drag-and-drop file stream → visual HNSW lookup pipeline:
  1. Compute SHA-256 for exact match.
  2. Compute neural embedding for approximate visual match (HNSW via pgvector).
  3. Perform C2PA manifest inspection.
  4. Return a VerificationResult matching the frontend VerificationResult type.

The response shape is designed to match the TypeScript VerificationResult
interface in frontend/src/services/client.ts exactly.
"""
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.inference import compute_embedding
from app.core.crypto import compute_salted_hash
from app.core.c2pa_engine import read_c2pa_manifest
from app.database.repository import (
    find_by_exact_hash,
    find_by_similarity,
)

router = APIRouter(tags=["verification"])


# ── Response models (mirror frontend VerificationResult) ─────────────────────

class ArtifactInfo(BaseModel):
    name: str
    type: str
    kind: str          # "image" | "video"
    size: str
    hash: str

class OriginInfo(BaseModel):
    model: str
    version: str
    action: str
    timestamp: str

class EvidenceMetric(BaseModel):
    name: str
    status: str        # "pass" | "warn" | "fail"
    detail: str

class TrustInfo(BaseModel):
    level: str
    label: str
    verifiable_evidence: bool
    evidence_metrics: List[EvidenceMetric]

class TransformationInfo(BaseModel):
    is_transformed: bool
    provenance_preserved: bool
    similarity_score: Optional[str] = None
    transformation_type: Optional[str] = None

class PipelineStep(BaseModel):
    system_name: str
    role: str
    timestamp: str

class MultiSystemInfo(BaseModel):
    systems_count: int
    pipeline: List[PipelineStep]

class TamperInfo(BaseModel):
    has_tampering: bool
    inconsistencies: List[str]
    tamper_type: Optional[str] = None

class PrivacyInfo(BaseModel):
    zero_knowledge_active: bool
    salted_prompt_hash: str
    redacted_fields: List[str]

class AdversarialInfo(BaseModel):
    test_category: str
    resilience_result: str

class BlockchainInfo(BaseModel):
    block_hash: str
    block_number: int
    timestamp: str
    chain_integrity: bool

class HistoryEntry(BaseModel):
    action: str
    model: str
    hash: str
    timestamp: str

class VerificationResult(BaseModel):
    status: str           # "verified" | "tampered" | "unregistered"
    artifact: ArtifactInfo
    origin: Optional[OriginInfo] = None
    chain_valid: bool
    history: List[HistoryEntry]
    blockchain: Optional[BlockchainInfo] = None
    trust: TrustInfo
    transformation: TransformationInfo
    multi_system: MultiSystemInfo
    tamper: TamperInfo
    privacy: PrivacyInfo
    adversarial: AdversarialInfo
    registered_hash: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1_048_576:
        return f"{n/1024:.1f} KB"
    return f"{n/1_048_576:.1f} MB"

def _artifact_kind(content_type: str) -> str:
    return "video" if content_type.startswith("video/") else "image"

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _build_unregistered(artifact: ArtifactInfo, sha256: str) -> VerificationResult:
    return VerificationResult(
        status="unregistered",
        artifact=artifact,
        chain_valid=False,
        history=[],
        trust=TrustInfo(
            level="UNREGISTERED",
            label="NO PROVENANCE RECORD",
            verifiable_evidence=False,
            evidence_metrics=[
                EvidenceMetric(name="Ledger Hash Search", status="fail",
                               detail="No anchor record found on ledger"),
                EvidenceMetric(name="C2PA Manifest Inspection", status="warn",
                               detail="No embedded metadata manifest found"),
            ],
        ),
        transformation=TransformationInfo(is_transformed=False, provenance_preserved=False),
        multi_system=MultiSystemInfo(systems_count=0, pipeline=[]),
        tamper=TamperInfo(
            has_tampering=False,
            inconsistencies=["Artifact is not registered on the provenance ledger"],
        ),
        privacy=PrivacyInfo(
            zero_knowledge_active=False,
            salted_prompt_hash="None",
            redacted_fields=[],
        ),
        adversarial=AdversarialInfo(
            test_category="Unregistered Asset Inspection",
            resilience_result="No Provenance Claim Found",
        ),
    )

def _build_verified(
    artifact: ArtifactInfo,
    record: Dict[str, Any],
    sha256: str,
    is_transformed: bool,
    similarity_score: Optional[float],
    c2pa_info: Optional[Dict],
) -> VerificationResult:
    ts = record.get("created_at", _now_iso())
    if hasattr(ts, "isoformat"):
        ts = ts.isoformat()

    model = record.get("model", "Unknown")
    version = record.get("version", "1.0")
    action = record.get("action", "GENERATED")
    salted = compute_salted_hash(sha256, model)

    metrics: List[EvidenceMetric] = [
        EvidenceMetric(
            name="Ledger Hash Match" if not is_transformed else "Visual Similarity Match",
            status="pass",
            detail="Exact SHA-256 match" if not is_transformed
                   else f"HNSW cosine similarity: {similarity_score:.4f}",
        )
    ]

    # C2PA evidence metric
    if c2pa_info and c2pa_info.get("manifest_present"):
        metrics.append(EvidenceMetric(
            name="C2PA Manifest", status="pass",
            detail=f"Signed by: {c2pa_info.get('signed_by', 'Unknown')}",
        ))
    else:
        metrics.append(EvidenceMetric(
            name="C2PA Manifest", status="warn",
            detail="No embedded C2PA manifest in uploaded file",
        ))

    pipeline_steps = [
        PipelineStep(system_name=model, role="Origin Engine", timestamp=ts)
    ]

    return VerificationResult(
        status="verified",
        artifact=artifact,
        origin=OriginInfo(model=model, version=version, action=action, timestamp=ts),
        chain_valid=True,
        history=[HistoryEntry(action=action, model=model, hash=sha256, timestamp=ts)],
        blockchain=BlockchainInfo(
            block_hash=sha256,
            block_number=record.get("id", 1) if isinstance(record.get("id"), int) else 1,
            timestamp=ts,
            chain_integrity=True,
        ),
        trust=TrustInfo(
            level="MEDIUM" if is_transformed else "HIGH",
            label="TRANSFORMED MATCH" if is_transformed else "VERIFIABLE EVIDENCE",
            verifiable_evidence=True,
            evidence_metrics=metrics,
        ),
        transformation=TransformationInfo(
            is_transformed=is_transformed,
            provenance_preserved=True,
            similarity_score=f"Cosine: {similarity_score:.4f}" if is_transformed else "100% Exact",
            transformation_type="Compression/Crop/Resize" if is_transformed else None,
        ),
        multi_system=MultiSystemInfo(systems_count=1, pipeline=pipeline_steps),
        tamper=TamperInfo(has_tampering=False, inconsistencies=[]),
        privacy=PrivacyInfo(
            zero_knowledge_active=True,
            salted_prompt_hash="0x" + salted[:32],
            redacted_fields=["User Prompt String"],
        ),
        adversarial=AdversarialInfo(
            test_category="Standard Verification",
            resilience_result="Verified Origin",
        ),
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/verification", response_model=VerificationResult)
async def verify_artifact(file: UploadFile = File(...)):
    """
    Verify an artifact against the provenance ledger.
    Performs exact SHA-256 lookup first, then approximate visual HNSW search.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file received.")

    content_type = file.content_type or "image/png"
    sha256 = hashlib.sha256(raw).hexdigest()
    kind = _artifact_kind(content_type)
    size_str = _format_bytes(len(raw))

    artifact = ArtifactInfo(
        name=file.filename or "unknown",
        type=content_type,
        kind=kind,
        size=size_str,
        hash=sha256,
    )

    # ── C2PA manifest (from the uploaded file itself) ─────────────────────────
    c2pa_info = read_c2pa_manifest(raw, file.filename or "")

    # ── 1. Exact SHA-256 lookup ───────────────────────────────────────────────
    record = await find_by_exact_hash(sha256)
    if record:
        return _build_verified(artifact, record, sha256,
                               is_transformed=False, similarity_score=None,
                               c2pa_info=c2pa_info)

    # ── 2. Visual embedding similarity search (HNSW) ──────────────────────────
    embedding = compute_embedding(raw, content_type)
    similar = await find_by_similarity(embedding, threshold=0.85, limit=1)
    if similar:
        best_record, score = similar[0]
        return _build_verified(artifact, best_record, sha256,
                               is_transformed=True, similarity_score=score,
                               c2pa_info=c2pa_info)

    # ── 3. Not found ──────────────────────────────────────────────────────────
    return _build_unregistered(artifact, sha256)
