"""
ModelLedger Evidence - Record

Defines the final EvidenceRecord and builds it by running the
collectors for one asset.

This module ONLY assembles evidence.

It does NOT:
- decide whether content is authentic
- decide whether content was AI-generated
- assign a trust score
- produce the final ModelLedger verdict

Record layout (see EvidenceRecord):

    schema_version
    asset          name, size, sha256
    metadata       clean ExifTool metadata        (None if not collected)
    c2pa           C2PA manifest evidence         (None if not collected)
    ai_signals     embedded AI-generation signals (None if not collected)
    model_matches  known generator names found in the signals
    summary        flat facts derived from the sections above
    errors         collector failures, as readable strings
    tools          which tools collected the evidence (+ version, status)
    receipt        integrity receipt over the payload and tools

`None` for a section always means "not collected" (see `errors` and
`tools`), never "collected and empty". A collector that failed is
recorded, never silently turned into empty evidence.

`summary` holds facts only. A field is None when its collector did not
run, so "unknown" is never confused with "false".
"""

from __future__ import annotations

import hashlib
import platform
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from .ai_signals import AISignalEvidence, AISignalsError, collect_ai_signals
from .c2pa import (
    AI_SOURCE_TYPES,
    C2PAError,
    C2PAEvidence,
    C2PANotInstalledError,
    read_c2pa,
)
from .metadata import (
    ExifToolNotFoundError,
    MetadataError,
    MetadataEvidence,
    read_metadata,
)
from .model_registry import ModelMatch, resolve_signals
from .receipts import (
    STATUS_FAILED,
    STATUS_NOT_INSTALLED,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_SUPPLIED,
    Receipt,
    ToolRecord,
    create_receipt,
    python_package_tool,
    verify_receipt,
)

EVIDENCE_PACKAGE_VERSION = "0.1.0"
RECORD_SCHEMA_VERSION = 2
_CHUNK = 1024 * 1024


class RecordError(Exception):
    """Base exception for record errors."""


class RecordFileNotFoundError(RecordError):
    """Raised when the asset does not exist."""


class InvalidRecordFileError(RecordError):
    """Raised when the supplied path is not a regular file."""


@dataclass(frozen=True)
class AssetInfo:
    """Identity of the asset the evidence is about."""

    name: str  # file name only, never a directory path
    size: int
    sha256: str


@dataclass(frozen=True)
class EvidenceSummary:
    """
    Flat facts derived from the evidence sections.

    These are observations, not conclusions. None means the relevant
    collector did not run.
    """

    c2pa_present: bool | None = None
    c2pa_validation_state: str | None = None
    c2pa_signing_credential_trusted: bool | None = None
    c2pa_has_ai_action: bool | None = None
    ai_signal_count: int | None = None
    declared_source_types: list[str] = field(default_factory=list)
    declared_ai_source_type: bool | None = None
    model_names: list[str] = field(default_factory=list)
    metadata_has_exif: bool | None = None
    metadata_has_xmp: bool | None = None
    camera: str | None = None
    capture_date_original: str | None = None
    gps_present: bool | None = None
    collector_errors: int = 0


@dataclass(frozen=True)
class EvidenceRecord:
    """The final evidence record for one asset. See module docstring."""

    asset: AssetInfo
    metadata: MetadataEvidence | None = None
    c2pa: C2PAEvidence | None = None
    ai_signals: AISignalEvidence | None = None
    model_matches: list[ModelMatch] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    tools: list[ToolRecord] = field(default_factory=list)
    receipt: Receipt | None = None
    schema_version: int = RECORD_SCHEMA_VERSION

    def summary(self) -> EvidenceSummary:
        return summarize(self)

    def payload(self) -> dict[str, Any]:
        """
        The receipted content: the evidence itself.

        Excludes the receipt and the tool list (the receipt binds the
        tools separately). Contains no timestamp, so identical evidence
        for an identical asset always yields an identical payload hash.
        """

        ai = None
        if self.ai_signals is not None:
            ai = asdict(self.ai_signals)
            ai["found"] = self.ai_signals.found

        return {
            "schema_version": self.schema_version,
            "asset": asdict(self.asset),
            "metadata": asdict(self.metadata) if self.metadata else None,
            "c2pa": asdict(self.c2pa) if self.c2pa else None,
            "ai_signals": ai,
            "model_matches": [asdict(m) for m in self.model_matches],
            "summary": asdict(self.summary()),
            "errors": list(self.errors),
        }

    def to_dict(self) -> dict[str, Any]:
        data = self.payload()
        data["tools"] = [tool.to_dict() for tool in self.tools]
        data["receipt"] = self.receipt.to_dict() if self.receipt else None
        return data

    def verify(self) -> bool:
        """
        True if the receipt exists and still matches this record:
        payload, asset hash, and tool list are all unchanged.
        """

        if self.receipt is None:
            return False

        return (
            verify_receipt(self.receipt, self.payload())
            and self.receipt.asset_sha256 == self.asset.sha256
            and self.receipt.tools == tuple(self.tools)
        )


# --------------------------------------------------------------------- #
# summary
# --------------------------------------------------------------------- #


def summarize(record: EvidenceRecord) -> EvidenceSummary:
    """Derive the flat summary from a record's sections."""

    values: dict[str, Any] = {"collector_errors": len(record.errors)}

    c2pa = record.c2pa
    if c2pa is not None:
        values.update(
            c2pa_present=c2pa.present,
            c2pa_validation_state=c2pa.validation_state,
            c2pa_signing_credential_trusted=c2pa.signing_credential_trusted,
            c2pa_has_ai_action=c2pa.has_ai_action,
        )

    terms: list[str] = [
        a.digital_source_type
        for a in (c2pa.actions if c2pa else [])
        if a.digital_source_type
    ]

    ai = record.ai_signals
    if ai is not None:
        values["ai_signal_count"] = len(ai.signals)
        terms += [s.value for s in ai.signals if s.kind == "digital_source_type"]

    meta = record.metadata
    if meta is not None:
        provenance_term = meta.provenance.get("digital_source_type")
        if provenance_term:
            terms.append(provenance_term)

        make = meta.camera.get("make")
        model = meta.camera.get("model")
        values.update(
            metadata_has_exif=meta.embedded.get("has_exif"),
            metadata_has_xmp=meta.embedded.get("has_xmp"),
            camera=" ".join(p for p in (make, model) if p) or None,
            capture_date_original=meta.dates.get("original"),
            gps_present=meta.location.get("gps_present"),
        )

    if c2pa is not None or ai is not None or meta is not None:
        distinct = list(dict.fromkeys(terms))
        values["declared_source_types"] = distinct
        values["declared_ai_source_type"] = any(
            t.lower() in AI_SOURCE_TYPES for t in distinct
        )

    values["model_names"] = sorted({m.name for m in record.model_matches})

    return EvidenceSummary(**values)


# --------------------------------------------------------------------- #
# building
# --------------------------------------------------------------------- #


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _own_tool(name: str, purpose: str, status: str = STATUS_OK) -> ToolRecord:
    return ToolRecord(
        name=name,
        version=EVIDENCE_PACKAGE_VERSION,
        purpose=purpose,
        status=status,
    )


def _short(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    return text if len(text) <= 300 else text[:300] + "..."


def build_record(
    path: str | Path,
    asset_sha256: str | None = None,
    metadata: MetadataEvidence | None = None,
    collect_metadata: bool = True,
    include_gps: bool = False,
    previous_receipt_hash: str | None = None,
    issue_receipt: bool = True,
) -> EvidenceRecord:
    """
    Collect evidence for an asset and assemble an EvidenceRecord.

    Args:
        path: path to the asset.
        asset_sha256: precomputed digest (e.g. from hash.py); computed
            here if omitted.
        metadata: precomputed MetadataEvidence; read here if omitted.
        collect_metadata: set False to skip ExifTool entirely.
        include_gps: include GPS coordinates in metadata (default False).
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
    tools: list[ToolRecord] = []

    # --- hash -------------------------------------------------------- #
    if asset_sha256:
        digest = asset_sha256
        tools.append(
            ToolRecord("sha256", None, "asset hash", STATUS_SUPPLIED)
        )
    else:
        digest = _sha256_file(asset_path)
        tools.append(
            ToolRecord(
                "python-hashlib", platform.python_version(),
                "asset SHA-256", STATUS_OK,
            )
        )

    # --- metadata ---------------------------------------------------- #
    metadata_evidence = metadata
    if metadata is not None:
        tools.append(
            ToolRecord(
                "exiftool", metadata.tool_version,
                "metadata extraction", STATUS_SUPPLIED,
            )
        )
    elif collect_metadata:
        try:
            metadata_evidence = read_metadata(
                asset_path, include_gps=include_gps
            )
            tools.append(
                ToolRecord(
                    "exiftool", metadata_evidence.tool_version,
                    "metadata extraction", STATUS_OK,
                )
            )
        except ExifToolNotFoundError as exc:
            errors.append(f"metadata: {_short(exc)}")
            tools.append(
                ToolRecord(
                    "exiftool", None, "metadata extraction",
                    STATUS_NOT_INSTALLED,
                )
            )
        except MetadataError as exc:
            errors.append(f"metadata: {_short(exc)}")
            tools.append(
                ToolRecord(
                    "exiftool", None, "metadata extraction",
                    STATUS_FAILED, _short(exc),
                )
            )
    else:
        tools.append(
            ToolRecord(
                "exiftool", None, "metadata extraction", STATUS_SKIPPED
            )
        )

    # --- c2pa -------------------------------------------------------- #
    c2pa_purpose = "C2PA manifest reading and validation"
    c2pa_evidence: C2PAEvidence | None = None
    try:
        c2pa_evidence = read_c2pa(asset_path)
        tools.append(python_package_tool("c2pa-python", c2pa_purpose))
    except C2PANotInstalledError as exc:
        errors.append(f"c2pa: {_short(exc)}")
        tools.append(
            python_package_tool(
                "c2pa-python", c2pa_purpose, STATUS_NOT_INSTALLED
            )
        )
    except C2PAError as exc:
        errors.append(f"c2pa: {_short(exc)}")
        tools.append(
            python_package_tool(
                "c2pa-python", c2pa_purpose, STATUS_FAILED, _short(exc)
            )
        )

    # --- ai signals + registry --------------------------------------- #
    signals_purpose = "AI signal extraction (PNG text, XMP, C2PA)"
    registry_purpose = "generator name resolution"
    ai_evidence: AISignalEvidence | None = None
    matches: list[ModelMatch] = []
    try:
        ai_evidence = collect_ai_signals(asset_path, c2pa_evidence)
        matches = resolve_signals(ai_evidence.signals)
        tools.append(_own_tool("modelledger.ai_signals", signals_purpose))
        tools.append(_own_tool("modelledger.model_registry", registry_purpose))
    except AISignalsError as exc:
        errors.append(f"ai_signals: {_short(exc)}")
        tools.append(
            ToolRecord(
                "modelledger.ai_signals", EVIDENCE_PACKAGE_VERSION,
                signals_purpose, STATUS_FAILED, _short(exc),
            )
        )
        tools.append(
            _own_tool(
                "modelledger.model_registry", registry_purpose,
                STATUS_SKIPPED,
            )
        )

    record = EvidenceRecord(
        asset=AssetInfo(
            name=asset_path.name,
            size=asset_path.stat().st_size,
            sha256=digest,
        ),
        metadata=metadata_evidence,
        c2pa=c2pa_evidence,
        ai_signals=ai_evidence,
        model_matches=matches,
        errors=errors,
        tools=tools,
    )

    if issue_receipt:
        record = replace(
            record,
            receipt=create_receipt(
                digest,
                record.payload(),
                tools=record.tools,
                previous_receipt_hash=previous_receipt_hash,
            ),
        )

    return record


__all__ = [
    "EVIDENCE_PACKAGE_VERSION",
    "RECORD_SCHEMA_VERSION",
    "AssetInfo",
    "EvidenceRecord",
    "EvidenceSummary",
    "InvalidRecordFileError",
    "RecordError",
    "RecordFileNotFoundError",
    "build_record",
    "summarize",
]