
"""
ModelLedger Evidence - Receipts

Tamper-evident receipts for collected evidence.

A receipt binds together:
- the SHA-256 of the asset
- the SHA-256 of the canonical evidence payload
- a UTC timestamp
- optionally, the hash of the previous receipt (forming a chain)

This module ONLY provides integrity checking.

It does NOT:
- sign anything (there are no keys here)
- prove WHO created a receipt
- decide authenticity or AI generation
- produce the final ModelLedger verdict

A valid receipt shows the payload has not changed since the receipt
was made. It does not show the payload is true, and anyone who can
rewrite both payload and receipt can forge a consistent pair. For
issuer authenticity, sign the receipt hash with a real key elsewhere.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

RECEIPT_VERSION = 1


class ReceiptError(Exception):
    """Base exception for receipt errors."""


class InvalidReceiptError(ReceiptError):
    """Raised when receipt data is malformed."""


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
        previous_receipt_hash: receipt_hash of the prior receipt, if chained.
        receipt_hash: SHA-256 over every other field.
        version: receipt format version.
    """

    asset_sha256: str
    payload_sha256: str
    created_at: str
    receipt_hash: str
    previous_receipt_hash: str | None = None
    version: int = RECEIPT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "asset_sha256": self.asset_sha256,
            "payload_sha256": self.payload_sha256,
            "created_at": self.created_at,
            "previous_receipt_hash": self.previous_receipt_hash,
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
) -> str:
    return sha256_hex(
        canonical_json(
            {
                "version": version,
                "asset_sha256": asset_sha256,
                "payload_sha256": payload_sha256,
                "created_at": created_at,
                "previous_receipt_hash": previous_receipt_hash,
            }
        )
    )


def create_receipt(
    asset_sha256: str,
    payload: Any,
    previous_receipt_hash: str | None = None,
    created_at: str | None = None,
) -> Receipt:
    """
    Create a receipt for an evidence payload.

    Args:
        asset_sha256: SHA-256 hex digest of the asset.
        payload: JSON-serializable evidence payload.
        previous_receipt_hash: receipt_hash of the previous receipt, to chain.
        created_at: override timestamp (UTC ISO-8601); defaults to now.
    """

    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    p_hash = payload_hash(payload)

    return Receipt(
        asset_sha256=asset_sha256,
        payload_sha256=p_hash,
        created_at=created_at,
        previous_receipt_hash=previous_receipt_hash,
        receipt_hash=_compute_receipt_hash(
            RECEIPT_VERSION, asset_sha256, p_hash, created_at,
            previous_receipt_hash,
        ),
    )


def verify_receipt(receipt: Receipt, payload: Any) -> bool:
    """
    True if the receipt is internally consistent AND matches payload.

    Checks both that the receipt's own hash is intact and that the
    payload still hashes to the value the receipt recorded.
    """

    expected = _compute_receipt_hash(
        receipt.version,
        receipt.asset_sha256,
        receipt.payload_sha256,
        receipt.created_at,
        receipt.previous_receipt_hash,
    )

    return (
        expected == receipt.receipt_hash
        and payload_hash(payload) == receipt.payload_sha256
    )


def verify_chain(receipts: Iterable[Receipt]) -> bool:
    """
    True if receipts (oldest first) are individually intact and each
    one's previous_receipt_hash equals the prior receipt_hash.

    The first receipt may have any previous_receipt_hash (a chain can
    start mid-ledger). This checks receipt integrity only; payloads
    are verified separately with verify_receipt().
    """

    previous_hash: str | None = None
    first = True

    for receipt in receipts:
        expected = _compute_receipt_hash(
            receipt.version,
            receipt.asset_sha256,
            receipt.payload_sha256,
            receipt.created_at,
            receipt.previous_receipt_hash,
        )
        if expected != receipt.receipt_hash:
            return False

        if not first and receipt.previous_receipt_hash != previous_hash:
            return False

        previous_hash = receipt.receipt_hash
        first = False

    return True


__all__ = [
    "RECEIPT_VERSION",
    "ReceiptError",
    "InvalidReceiptError",
    "Receipt",
    "canonical_json",
    "payload_hash",
    "create_receipt",
    "verify_receipt",
    "verify_chain",
]