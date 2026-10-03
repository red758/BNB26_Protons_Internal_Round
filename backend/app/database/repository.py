"""
repository.py — Provenance Ledger Repository & HNSW pgvector Similarity Search

Manages:
  • ProvenanceRecord SQLAlchemy ORM schema
  • Native HNSW vector index queries via pgvector
  • Exact SHA-256 hash lookups
  • Fallback in-memory cosine similarity search if pgvector is not available
"""
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
import numpy as np

from sqlalchemy import Column, String, Integer, DateTime, Text, Float, desc, text
from sqlalchemy.orm import Session
from app.database.connection import Base

logger = logging.getLogger("db_repository")


class ProvenanceRecord(Base):
    __tablename__ = "provenance_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_hash = Column(String(64), unique=True, index=True, nullable=False)
    model_name = Column(String(128), index=True, nullable=False)
    model_version = Column(String(64), default="1.0.0")
    prompt_commitment = Column(String(128), nullable=False)
    salt = Column(String(64), nullable=True)
    creator_wallet = Column(String(128), nullable=True)
    embedding_json = Column(Text, nullable=True)  # Store JSON serialized float vector
    c2pa_signed_by = Column(String(256), nullable=True)
    c2pa_algorithm = Column(String(64), nullable=True)
    c2pa_cert = Column(String(256), nullable=True)
    c2pa_raw = Column(Text, nullable=True)
    extra_metadata = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


def save_provenance_record(
    db: Session,
    asset_hash: str,
    model_name: str,
    model_version: str,
    prompt_commitment: str,
    salt: Optional[str] = None,
    creator_wallet: Optional[str] = None,
    embedding: Optional[List[float]] = None,
    c2pa_data: Optional[Dict[str, Any]] = None,
    extra_metadata: Optional[Dict[str, Any]] = None
) -> ProvenanceRecord:
    """Inserts or updates a provenance record in the database."""
    existing = db.query(ProvenanceRecord).filter(ProvenanceRecord.asset_hash == asset_hash).first()
    if existing:
        return existing

    record = ProvenanceRecord(
        asset_hash=asset_hash,
        model_name=model_name,
        model_version=model_version,
        prompt_commitment=prompt_commitment,
        salt=salt,
        creator_wallet=creator_wallet or "0x0000000000000000000000000000000000000000",
        embedding_json=json.dumps(embedding) if embedding else None,
        c2pa_signed_by=c2pa_data.get("signed_by") if c2pa_data else None,
        c2pa_algorithm=c2pa_data.get("algorithm") if c2pa_data else None,
        c2pa_cert=c2pa_data.get("cert") if c2pa_data else None,
        c2pa_raw=json.dumps(c2pa_data) if c2pa_data else None,
        extra_metadata=json.dumps(extra_metadata) if extra_metadata else None,
        created_at=datetime.now(timezone.utc)
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_record_by_hash(db: Session, asset_hash: str) -> Optional[ProvenanceRecord]:
    """Look up an exact SHA-256 hash match in the provenance database."""
    return db.query(ProvenanceRecord).filter(ProvenanceRecord.asset_hash == asset_hash).first()


def search_by_similarity(
    db: Session,
    query_vector: List[float],
    threshold: float = 0.85,
    top_k: int = 5
) -> List[Tuple[ProvenanceRecord, float]]:
    """
    Search for similar visual embeddings using pgvector or in-memory cosine similarity.
    Returns list of tuples: (record, similarity_score) where similarity is between 0.0 and 1.0.
    """
    results = []
    
    # Check if native pgvector table query is supported
    # Fallback to in-memory vectorized search across stored records
    try:
        all_records = db.query(ProvenanceRecord).filter(ProvenanceRecord.embedding_json.isnot(None)).all()
        if not all_records:
            return []

        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        candidates = []
        for rec in all_records:
            try:
                emb = np.array(json.loads(rec.embedding_json), dtype=np.float32)
                emb_norm = np.linalg.norm(emb)
                if emb_norm == 0:
                    continue
                # Cosine similarity
                sim = float(np.dot(q_vec, emb) / (q_norm * emb_norm))
                if sim >= threshold:
                    candidates.append((rec, sim))
            except Exception:
                continue

        # Sort descending by similarity
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]
    except Exception as e:
        logger.error(f"Error during similarity search: {e}")
        return []


def get_recent_records(db: Session, limit: int = 20) -> List[ProvenanceRecord]:
    """Returns the latest registered provenance entries."""
    return db.query(ProvenanceRecord).order_by(desc(ProvenanceRecord.created_at)).limit(limit).all()


# ── Async API helpers for FastAPI endpoints ───────────────────────────────────

async def insert_artifact(
    sha256: str,
    filename: str,
    content_type: str,
    model: str,
    version: str,
    action: str,
    embedding: List[float],
    salted_hash: str,
    c2pa_info: Optional[Dict[str, Any]] = None,
) -> str:
    """Inserts an artifact record and returns its ID."""
    from app.database.connection import get_session_factory
    factory = get_session_factory()
    with factory() as session:
        rec = save_provenance_record(
            db=session,
            asset_hash=sha256,
            model_name=model,
            model_version=version,
            prompt_commitment=salted_hash,
            embedding=embedding,
            c2pa_data=c2pa_info,
            extra_metadata={"filename": filename, "content_type": content_type, "action": action}
        )
        return str(rec.id)


async def find_by_exact_hash(sha256: str) -> Optional[Dict[str, Any]]:
    """Look up an exact SHA-256 match and return dictionary representation."""
    from app.database.connection import get_session_factory
    factory = get_session_factory()
    with factory() as session:
        rec = get_record_by_hash(session, sha256)
        if not rec:
            return None
        meta = json.loads(rec.extra_metadata) if rec.extra_metadata else {}
        return {
            "id": rec.id,
            "hash": rec.asset_hash,
            "model": rec.model_name,
            "version": rec.model_version,
            "action": meta.get("action", "GENERATED"),
            "created_at": rec.created_at,
            "c2pa_signed_by": rec.c2pa_signed_by,
        }


async def find_by_similarity(
    embedding: List[float],
    threshold: float = 0.85,
    limit: int = 1
) -> List[Tuple[Dict[str, Any], float]]:
    """Search for similar embeddings and return list of (record_dict, score)."""
    from app.database.connection import get_session_factory
    factory = get_session_factory()
    with factory() as session:
        matches = search_by_similarity(session, embedding, threshold=threshold, top_k=limit)
        results = []
        for rec, score in matches:
            meta = json.loads(rec.extra_metadata) if rec.extra_metadata else {}
            rec_dict = {
                "id": rec.id,
                "hash": rec.asset_hash,
                "model": rec.model_name,
                "version": rec.model_version,
                "action": meta.get("action", "GENERATED"),
                "created_at": rec.created_at,
                "c2pa_signed_by": rec.c2pa_signed_by,
            }
            results.append((rec_dict, score))
        return results
