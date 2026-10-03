"""
ModelLedger Evidence - Receipts

Tamper-evident receipts for collected evidence.

A receipt binds together:
- the SHA-256 of the asset
- the SHA-256 of the canonical evidence payload
- the tools that collected the evidence (name, version, status)
- a UTC timestamp
- optionally, the hash of the previous receipt (forming a chain)

This module ONLY provides integrity checking and tool bookkeeping.

It does NOT:
- sign anything (there are no keys here)
- prove WHO created a receipt
- decide authenticity or AI generation
- produce the final ModelLedger verdict

A valid receipt shows the payload and tool list have not changed since
the receipt was made. It does not show the evidence is true, and anyone
who can rewrite both payload and receipt can forge a consistent pair.
For issuer authenticity, sign the receipt hash with a real key elsewhere.

Receipt version 2 added `tools`. Version 1 receipts (no tools) still
verify.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from typing import Any, Iterable

RECEIPT_VERSION = 2

# ToolRecord.status values
STATUS_OK = "ok"
STATUS_FAILED = "failed"
STATUS_NOT_INSTALLED = "not_installed"
STATUS_SUPPLIED = "supplied"  # result came from the caller, not run here
STATUS_SKIPPED = "skipped"


class ReceiptError(Exception):
    """Base exception for receipt errors."""


class InvalidReceiptError(ReceiptError):
    """Raised when receipt data is malformed."""


@dataclass(frozen=True)
class ToolRecord:
    """
    A tool involved in collecting evidence.

    Attributes:
        name: tool or package name, e.g. "exiftool", "c2pa-python".
        version: exact version string, or None if unknown/unavailable.
        purpose: what it was used for.
        status: STATUS_* value. A tool that failed or was missing is
            recorded too, so a record never implies a collector ran
            when it did not.
        detail: short note (e.g. the failure reason), optional.
    """

    name: str
    version: str | None
    purpose: str
    status: str = STATUS_OK
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "purpose": self.purpose,
            "status": self.status,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolRecord":
        try:
            return cls(
                name=str(data["name"]),
                version=data.get("version"),
                purpose=str(data["purpose"]),
                status=str(data.get("status", STATUS_OK)),
                detail=data.get("detail"),
            )
        except (KeyError, TypeError) as exc:
            raise InvalidReceiptError(f"Malformed tool record: {exc}") from exc


def python_package_version(distribution: str) -> str | None:
    """Installed version of a Python distribution, or None."""
    try:
        return importlib_metadata.version(distribution)
    except importlib_metadata.PackageNotFoundError:
        return None


def python_package_tool(
    distribution: str,
    purpose: str,
    status: str = STATUS_OK,
    detail: str | None = None,
    name: str | None = None,
) -> ToolRecord:
    """ToolRecord for an installed Python package (version auto-detected)."""
    return ToolRecord(
        name=name or distribution,
        version=python_package_version(distribution),
        purpose=purpose,
        status=status,
        detail=detail,
    )


def canonical_json(value: Any) -> str:
    """
    Deterministic JSON: sorted keys, no whitespace, UTF-8 friendly.

    Raises TypeError if the value is not JSON-serializable, rather
    than guessing a representation.
    """

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def payload_hash(payload: Any) -> str:
    """SHA-256 of the canonical JSON form of a payload."""
    return sha256_hex(canonical_json(payload))


@dataclass(frozen=True)
class Receipt:
    """
    Integrity receipt for one evidence payload.

    Attributes:
        asset_sha256: SHA-256 of the asset the evidence is about.
        payload_sha256: SHA-256 of the canonical evidence payload.
        created_at: UTC ISO-8601 timestamp.
        receipt_hash: SHA-256 over every other field (including tools).
        previous_receipt_hash: receipt_hash of the prior receipt, if chained.
        tools: tools that collected the evidence.
        version: receipt format version.
    """

    asset_sha256: str
    payload_sha256: str
    created_at: str
    receipt_hash: str
    previous_receipt_hash: str | None = None
    tools: tuple[ToolRecord, ...] = ()
    version: int = RECEIPT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "asset_sha256": self.asset_sha256,
            "payload_sha256": self.payload_sha256,
            "created_at": self.created_at,
            "previous_receipt_hash": self.previous_receipt_hash,
            "tools": [tool.to_dict() for tool in self.tools],
            "receipt_hash": self.receipt_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Receipt":
        try:
            return cls(
                version=int(data["version"]),
                asset_sha256=str(data["asset_sha256"]),
                payload_sha256=str(data["payload_sha256"]),
                created_at=str(data["created_at"]),
                previous_receipt_hash=data.get("previous_receipt_hash"),
                tools=tuple(
                    ToolRecord.from_dict(t) for t in data.get("tools", [])
                ),
                receipt_hash=str(data["receipt_hash"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidReceiptError(f"Malformed receipt: {exc}") from exc


def _compute_receipt_hash(
    version: int,
    asset_sha256: str,
    payload_sha256: str,
    created_at: str,
    previous_receipt_hash: str | None,
    tools: Iterable[ToolRecord],
) -> str:
    body: dict[str, Any] = {
        "version": version,
        "asset_sha256": asset_sha256,
        "payload_sha256": payload_sha256,
        "created_at": created_at,
        "previous_receipt_hash": previous_receipt_hash,
    }

    if version >= 2:
        body["tools"] = [tool.to_dict() for tool in tools]

    return sha256_hex(canonical_json(body))


def _receipt_hash_of(receipt: Receipt) -> str:
    return _compute_receipt_hash(
        receipt.version,
        receipt.asset_sha256,
        receipt.payload_sha256,
        receipt.created_at,
        receipt.previous_receipt_hash,
        receipt.tools,
    )


def create_receipt(
    asset_sha256: str,
    payload: Any,
    tools: Iterable[ToolRecord] = (),
    previous_receipt_hash: str | None = None,
    created_at: str | None = None,
) -> Receipt:
    """
    Create a receipt for an evidence payload.

    Args:
        asset_sha256: SHA-256 hex digest of the asset.
        payload: JSON-serializable evidence payload.
        tools: tools that collected the evidence.
        previous_receipt_hash: receipt_hash of the previous receipt, to chain.
        created_at: override timestamp (UTC ISO-8601); defaults to now.
    """

    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    tools = tuple(tools)
    p_hash = payload_hash(payload)

    return Receipt(
        asset_sha256=asset_sha256,
        payload_sha256=p_hash,
        created_at=created_at,
        previous_receipt_hash=previous_receipt_hash,
        tools=tools,
        receipt_hash=_compute_receipt_hash(
            RECEIPT_VERSION, asset_sha256, p_hash, created_at,
            previous_receipt_hash, tools,
        ),
    )


def verify_receipt(receipt: Receipt, payload: Any) -> bool:
    """
    True if the receipt is internally consistent AND matches payload.

    Checks that the receipt's own hash (which covers the tool list) is
    intact and that the payload still hashes to what it recorded.
    """

    return (
        _receipt_hash_of(receipt) == receipt.receipt_hash
        and payload_hash(payload) == receipt.payload_sha256
    )


def verify_chain(receipts: Iterable[Receipt]) -> bool:
    """
    True if receipts (oldest first) are individually intact and each
    one's previous_receipt_hash equals the prior receipt_hash.

    The first receipt may have any previous_receipt_hash (a chain can
    start mid-ledger). Payloads are verified separately with
    verify_receipt().
    """

    previous_hash: str | None = None
    first = True

    for receipt in receipts:
        if _receipt_hash_of(receipt) != receipt.receipt_hash:
            return False

        if not first and receipt.previous_receipt_hash != previous_hash:
            return False

        previous_hash = receipt.receipt_hash
        first = False

    return True


__all__ = [
    "RECEIPT_VERSION",
    "STATUS_FAILED",
    "STATUS_NOT_INSTALLED",
    "STATUS_OK",
    "STATUS_SKIPPED",
    "STATUS_SUPPLIED",
    "InvalidReceiptError",
    "Receipt",
    "ReceiptError",
    "ToolRecord",
    "canonical_json",
    "create_receipt",
    "payload_hash",
    "python_package_tool",
    "python_package_version",
    "verify_chain",
    "verify_receipt",
]