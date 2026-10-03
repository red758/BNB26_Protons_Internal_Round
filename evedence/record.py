
"""
ModelLedger Evidence - Record

Assembles the evidence collected for one asset into a single record,
and attaches an integrity receipt.

This module ONLY assembles evidence.

It does NOT:
- decide whether content is authentic
- decide whether content was AI-generated
- assign a trust score
- produce the final ModelLedger verdict

If a collector fails, the failure is recorded in `errors` rather than
hidden or turned into fake evidence.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from .ai_signals import AISignalEvidence, AISignalsError, collect_ai_signals
from .c2pa import C2PAError, C2PAEvidence, read_c2pa
from .model_registry import ModelMatch, resolve_signals
from .receipts import Receipt, create_receipt, verify_receipt

RECORD_SCHEMA_VERSION = 1
_CHUNK = 1024 * 1024


class RecordError(Exception):
    """Base exception for record errors."""


class RecordFileNotFoundError(RecordError):
    """Raised when the asset does not exist."""


class InvalidRecordFileError(RecordError):
    """Raised when the supplied path is not a regular file."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class EvidenceRecord:
    """
    All evidence collected for one asset.

    Attributes:
        asset_name: file name only (no directory), to avoid leaking paths.
        asset_size: size in bytes.
        asset_sha256: SHA-256 of the asset.
        metadata: metadata evidence supplied by the caller, if any.
        c2pa: C2PA evidence, or None if collection failed (see errors).
        ai_signals: AI signal evidence, or None if collection failed.
        model_matches: registry names matched in the AI signals.
        errors: collector failures, as readable strings.
        receipt: integrity receipt over payload(), once issued.
        schema_version: record format version.
    """

    asset_name: str
    asset_size: int
    asset_sha256: str
    metadata: dict[str, Any] | None = None
    c2pa: C2PAEvidence | None = None
    ai_signals: AISignalEvidence | None = None
    model_matches: list[ModelMatch] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    receipt: Receipt | None = None
    schema_version: int = RECORD_SCHEMA_VERSION

    def payload(self) -> dict[str, Any]:
        """
        The receipted content: everything except the receipt itself.

        Contains no timestamp, so identical evidence for an identical
        asset always yields an identical payload hash.
        """

        ai = None
        if self.ai_signals is not None:
            ai = asdict(self.ai_signals)
            ai["found"] = self.ai_signals.found

        return {
            "schema_version": self.schema_version,
            "asset": {
                "name": self.asset_name,
                "size": self.asset_size,
                "sha256": self.asset_sha256,
            },
            "metadata": self.metadata,
            "c2pa": asdict(self.c2pa) if self.c2pa is not None else None,
            "ai_signals": ai,
            "model_matches": [asdict(m) for m in self.model_matches],
            "errors": list(self.errors),
        }

    def to_dict(self) -> dict[str, Any]:
        data = self.payload()
        data["receipt"] = self.receipt.to_dict() if self.receipt else None
        return data

    def verify(self) -> bool:
        """True if the receipt exists and still matches this record."""
        return self.receipt is not None and verify_receipt(
            self.receipt, self.payload()
        )


def build_record(
    path: str | Path,
    metadata: dict[str, Any] | None = None,
    asset_sha256: str | None = None,
    previous_receipt_hash: str | None = None,
    issue_receipt: bool = True,
) -> EvidenceRecord:
    """
    Collect evidence for an asset and assemble an EvidenceRecord.

    Args:
        path: path to the asset.
        metadata: output of the metadata collector, if you have it.
        asset_sha256: precomputed digest; computed here if omitted.
        previous_receipt_hash: receipt_hash of the prior record, to chain.
        issue_receipt: attach an integrity receipt (default True).

    Raises:
        RecordFileNotFoundError: the asset does not exist.
        InvalidRecordFileError: the path is not a regular file.
    """

    asset_path = Path(path)

    if not asset_path.exists():
        raise RecordFileNotFoundError(f"Asset does not exist: {asset_path}")

    if not asset_path.is_file():
        raise InvalidRecordFileError(
            f"Asset path is not a regular file: {asset_path}"
        )

    errors: list[str] = []

    digest = asset_sha256 or _sha256_file(asset_path)

    c2pa_evidence: C2PAEvidence | None = None
    try:
        c2pa_evidence = read_c2pa(asset_path)
    except C2PAError as exc:
        errors.append(f"c2pa: {type(exc).__name__}: {exc}")

    ai_evidence: AISignalEvidence | None = None
    try:
        ai_evidence = collect_ai_signals(asset_path, c2pa_evidence)
    except AISignalsError as exc:
        errors.append(f"ai_signals: {type(exc).__name__}: {exc}")

    matches = resolve_signals(ai_evidence.signals) if ai_evidence else []

    record = EvidenceRecord(
        asset_name=asset_path.name,
        asset_size=asset_path.stat().st_size,
        asset_sha256=digest,
        metadata=metadata,
        c2pa=c2pa_evidence,
        ai_signals=ai_evidence,
        model_matches=matches,
        errors=errors,
    )

    if issue_receipt:
        record = replace(
            record,
            receipt=create_receipt(
                digest, record.payload(), previous_receipt_hash
            ),
        )

    return record


__all__ = [
    "RECORD_SCHEMA_VERSION",
    "RecordError",
    "RecordFileNotFoundError",
    "InvalidRecordFileError",
    "EvidenceRecord",
    "build_record",
]