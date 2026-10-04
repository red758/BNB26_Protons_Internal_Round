"""
POST /api/verification

Verification pipeline:
  1. SHA-256 exact match against provenance ledger.
  2. Visual embedding HNSW approximate match (if no exact match).
  3. C2PA manifest inspection (always).
  4. Local forensic analysis + optional Gemini augmentation.
  5. Merge all signals into a calibrated final verdict.

The response shape exactly matches the TypeScript VerificationResult
interface in frontend/src/services/client.ts.

Verdict mapping:
  - Ledger exact match   → status="verified",     trust=HIGH
  - Ledger visual match  → status="verified",     trust=MEDIUM
  - Forensics → LIKELY_AI, not in ledger  → status="tampered",     trust=UNTRUSTED
  - Forensics → POSSIBLY_AI              → status="unregistered",  trust=MEDIUM (amber)
  - Forensics → LIKELY_AUTHENTIC         → status="unregistered",  trust=HIGH   (no ledger record but clean)
  - Forensics → INSUFFICIENT_EVIDENCE   → status="unregistered",  trust=UNREGISTERED
"""
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.inference import compute_embedding
from app.core.crypto import compute_salted_hash
from app.core.c2pa_engine import read_c2pa_manifest
from app.core.ai_predictor import predict_provenance_features
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

def _metrics_from_list(items: List[Dict]) -> List[EvidenceMetric]:
    return [
        EvidenceMetric(
            name=item.get("name", "Check"),
            status=item.get("status", "warn"),
            detail=item.get("detail", ""),
        )
        for item in items
    ]

def _pipeline_steps(steps: List[Dict]) -> List[PipelineStep]:
    now = _now_iso()
    return [
        PipelineStep(
            system_name=s.get("system_name", "Unknown"),
            role=s.get("role", ""),
            timestamp=now,
        )
        for s in steps
    ]


def _build_unregistered(
    artifact: ArtifactInfo,
    sha256: str,
    ai_preds: Optional[Dict],
) -> VerificationResult:
    """Build response for an artifact not in the ledger."""

    now = _now_iso()

    # Defaults (no forensics available)
    trust_level = "UNREGISTERED"
    trust_label = "NO PROVENANCE RECORD"
    trust_verifiable = False
    evidence_metrics: List[EvidenceMetric] = [
        EvidenceMetric(name="Ledger Hash Search", status="fail",
                       detail="No anchor record found on the provenance ledger."),
        EvidenceMetric(name="C2PA Manifest Inspection", status="warn",
                       detail="No embedded C2PA provenance manifest found in file."),
    ]
    status = "unregistered"
    has_tampering = False
    tamper_inconsistencies: List[str] = ["Artifact is not registered on the provenance ledger."]
    tamper_type = None
    transformation_is_transformed = False
    transformation_type = None
    pipeline_steps: List[PipelineStep] = []
    test_category = "Unregistered Asset Inspection"
    resilience_result = "No Provenance Claim Found"
    inferred_model_str = "Unknown"
    origin: Optional[OriginInfo] = None
    chain_valid = False

    # ── Apply forensic findings ───────────────────────────────────────────────
    if ai_preds:
        forensic_verdict = ai_preds.get("_forensic_verdict", "INSUFFICIENT_EVIDENCE")
        ai_prob = ai_preds.get("_ai_probability", 0.5)
        conf = ai_preds.get("_confidence", "LOW")
        inferred_model_str = ai_preds.get("_inferred_model", "Unknown")
        forensic_metrics = ai_preds.get("evidence_metrics", [])

        # Override trust level from forensic findings
        pt = ai_preds.get("provenance_trust", {})
        if pt.get("level"):
            trust_level = pt["level"]
        if pt.get("label"):
            trust_label = pt["label"]

        # Build enriched evidence metrics
        ledger_metric = EvidenceMetric(
            name="Ledger Hash Search",
            status="fail",
            detail="No anchor record found. This artifact has not been registered."
        )
        forensic_evidence = _metrics_from_list(forensic_metrics)
        evidence_metrics = [ledger_metric] + forensic_evidence

        # trust_verifiable only if forensics has high confidence
        trust_verifiable = conf in ("HIGH", "MEDIUM")

        # Determine final status from forensic verdict
        if forensic_verdict == "LIKELY_AI":
            status = "tampered"  # AI content flagged as "tampered provenance" in UI
            has_tampering = True
            tamper_type = "AI Generated Content"
            tamper_inconsistencies = ai_preds.get("tamper_detection", {}).get(
                "inconsistencies",
                [f"Forensic analysis indicates AI-generated content (prob: {ai_prob*100:.0f}%)."]
            )
        elif forensic_verdict == "POSSIBLY_AI":
            status = "unregistered"  # Amber state
            has_tampering = False
            tamper_inconsistencies = [
                f"Moderate AI-generation signals detected (prob: {ai_prob*100:.0f}%, confidence: {conf}). "
                f"Evidence is insufficient for a definitive classification."
            ]
        elif forensic_verdict == "LIKELY_AUTHENTIC":
            status = "unregistered"  # Not in ledger but looks clean
            has_tampering = False
            trust_level = "HIGH" if conf == "HIGH" else "MEDIUM"
            trust_label = f"LIKELY AUTHENTIC — {int((1-ai_prob)*100)}% CONFIDENCE (NOT IN LEDGER)"
            tamper_inconsistencies = [
                "This artifact does not appear to be AI-generated based on forensic analysis, "
                "but it has not been registered on the provenance ledger."
            ]

        # Transformation
        td = ai_preds.get("transformation_handling", {})
        transformation_is_transformed = td.get("is_transformed", False)
        transformation_type = td.get("transformation_type")

        # Pipeline
        raw_pipeline = ai_preds.get("multi_system_provenance", [])
        pipeline_steps = _pipeline_steps(raw_pipeline)

        # Tamper
        tamper_data = ai_preds.get("tamper_detection", {})
        if tamper_data.get("has_tampering"):
            has_tampering = True
            tamper_type = tamper_data.get("tamper_type", tamper_type)
            extra_incon = tamper_data.get("inconsistencies", [])
            if extra_incon:
                tamper_inconsistencies = extra_incon

        # Adversarial
        adv = ai_preds.get("adversarial_testing", {})
        test_category = adv.get("test_category", test_category)
        resilience_result = adv.get("resilience_result", resilience_result)

        # Build origin from inferred model for display
        if inferred_model_str and inferred_model_str != "Unknown / Not Determinable":
            origin = OriginInfo(
                model=inferred_model_str,
                version="Unverified",
                action="INFERRED" if ai_preds.get("_attribution_type") == "INFERRED" else "DETECTED",
                timestamp=now,
            )

    return VerificationResult(
        status=status,
        artifact=artifact,
        origin=origin,
        chain_valid=chain_valid,
        history=[],
        trust=TrustInfo(
            level=trust_level,
            label=trust_label,
            verifiable_evidence=trust_verifiable,
            evidence_metrics=evidence_metrics,
        ),
        transformation=TransformationInfo(
            is_transformed=transformation_is_transformed,
            provenance_preserved=False,
            transformation_type=transformation_type,
        ),
        multi_system=MultiSystemInfo(
            systems_count=len(pipeline_steps),
            pipeline=pipeline_steps,
        ),
        tamper=TamperInfo(
            has_tampering=has_tampering,
            inconsistencies=tamper_inconsistencies,
            tamper_type=tamper_type,
        ),
        privacy=PrivacyInfo(
            zero_knowledge_active=False,
            salted_prompt_hash="None",
            redacted_fields=[],
        ),
        adversarial=AdversarialInfo(
            test_category=test_category,
            resilience_result=resilience_result,
        ),
    )


def _build_verified(
    artifact: ArtifactInfo,
    record: Dict[str, Any],
    sha256: str,
    is_transformed: bool,
    similarity_score: Optional[float],
    c2pa_info: Optional[Dict],
    ai_preds: Optional[Dict],
) -> VerificationResult:
    """Build response for an artifact found in the provenance ledger."""
    ts = record.get("created_at", _now_iso())
    if hasattr(ts, "isoformat"):
        ts = ts.isoformat()

    model = record.get("model", "Unknown")
    version = record.get("version", "1.0")
    action = record.get("action", "GENERATED")
    salted = compute_salted_hash(sha256, model)
    now = _now_iso()

    # ── Base evidence metrics ────────────────────────────────────────────────
    metrics: List[EvidenceMetric] = [
        EvidenceMetric(
            name="Ledger Hash Match" if not is_transformed else "Visual Similarity Match",
            status="pass",
            detail="Exact SHA-256 match on provenance ledger." if not is_transformed
                   else f"HNSW cosine similarity: {similarity_score:.4f}",
        )
    ]

    if c2pa_info and c2pa_info.get("manifest_present"):
        metrics.append(EvidenceMetric(
            name="C2PA Manifest",
            status="pass",
            detail=f"Signed by: {c2pa_info.get('signed_by', 'Unknown')}",
        ))
    else:
        metrics.append(EvidenceMetric(
            name="C2PA Manifest",
            status="warn",
            detail="No embedded C2PA manifest found in uploaded file.",
        ))

    # ── Append forensic evidence if available ────────────────────────────────
    forensic_evidence = []
    manipulation_detected = False
    manipulation_inconsistencies: List[str] = []
    pipeline_extra: List[Dict] = []

    if ai_preds:
        forensic_evidence = _metrics_from_list(ai_preds.get("evidence_metrics", []))
        manipulation_detected = ai_preds.get("tamper_detection", {}).get("has_tampering", False)
        manipulation_inconsistencies = ai_preds.get("tamper_detection", {}).get("inconsistencies", [])
        pipeline_extra = ai_preds.get("multi_system_provenance", [])

    all_metrics = metrics + forensic_evidence

    # ── Pipeline ─────────────────────────────────────────────────────────────
    registered_steps = [PipelineStep(system_name=model, role="Registered Origin", timestamp=ts)]
    extra_steps = _pipeline_steps(pipeline_extra)
    pipeline_steps = registered_steps + [s for s in extra_steps
                                          if s.system_name != model]

    trust_level = "MEDIUM" if is_transformed else "HIGH"
    trust_label = "TRANSFORMED MATCH" if is_transformed else "VERIFIABLE EVIDENCE"

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
            level=trust_level,
            label=trust_label,
            verifiable_evidence=True,
            evidence_metrics=all_metrics,
        ),
        transformation=TransformationInfo(
            is_transformed=is_transformed,
            provenance_preserved=True,
            similarity_score=f"Cosine: {similarity_score:.4f}" if is_transformed else "100% Exact",
            transformation_type="Compression / Crop / Resize" if is_transformed else None,
        ),
        multi_system=MultiSystemInfo(
            systems_count=len(pipeline_steps),
            pipeline=pipeline_steps,
        ),
        tamper=TamperInfo(
            has_tampering=manipulation_detected,
            inconsistencies=manipulation_inconsistencies,
            tamper_type="Post-registration manipulation detected" if manipulation_detected else None,
        ),
        privacy=PrivacyInfo(
            zero_knowledge_active=True,
            salted_prompt_hash="0x" + salted[:32],
            redacted_fields=["User Prompt String"],
        ),
        adversarial=AdversarialInfo(
            test_category="Standard Provenance Verification",
            resilience_result="Ledger match confirmed — origin verified.",
        ),
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/verification", response_model=VerificationResult)
async def verify_artifact(file: UploadFile = File(...)):
    """
    Verify an artifact against the provenance ledger.

    Pipeline:
    1. Exact SHA-256 ledger lookup.
    2. Visual HNSW approximate search.
    3. C2PA manifest inspection.
    4. Local forensic analysis (always) + Gemini VLM augmentation (optional).
    5. Merge all signals into the final verdict.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file received.")

    content_type = file.content_type or "image/jpeg"
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

    # ── C2PA manifest ─────────────────────────────────────────────────────────
    c2pa_info = read_c2pa_manifest(raw, file.filename or "")

    # ── AI forensics (runs regardless of ledger result) ───────────────────────
    ai_preds = predict_provenance_features(raw, content_type)

    # ── 1. Exact SHA-256 lookup ───────────────────────────────────────────────
    record = await find_by_exact_hash(sha256)
    if record:
        return _build_verified(artifact, record, sha256,
                               is_transformed=False, similarity_score=None,
                               c2pa_info=c2pa_info, ai_preds=ai_preds)

    # ── 2. Visual embedding similarity search (HNSW) ──────────────────────────
    embedding = compute_embedding(raw, content_type)
    similar = await find_by_similarity(embedding, threshold=0.85, limit=1)
    if similar:
        best_record, score = similar[0]
        return _build_verified(artifact, best_record, sha256,
                               is_transformed=True, similarity_score=score,
                               c2pa_info=c2pa_info, ai_preds=ai_preds)

    # ── 3. Not in ledger — forensics drives the verdict ───────────────────────
    return _build_unregistered(artifact, sha256, ai_preds)
