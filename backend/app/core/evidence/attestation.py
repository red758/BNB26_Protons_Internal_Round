"""
ModelLedger Evidence - Execution Attestation

Provider-agnostic execution attestation evidence representation.

This module collects and validates attestation evidence only.
It does not fabricate hardware, TEE, TPM, signatures, or execution proof.
Final trust decisions belong to the Evidence Engine / Trust Policy layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


class AttestationError(Exception):
    """Base exception for ModelLedger attestation errors."""


class InvalidAttestationError(AttestationError):
    """Raised when attestation evidence is structurally invalid."""


class UnsupportedAttestationError(AttestationError):
    """Raised when an attestation type is unsupported."""


class AttestationVerificationError(AttestationError):
    """Raised when attestation verification cannot be completed."""


@dataclass(frozen=True)
class AttestationEvidence:
    """Structured execution-attestation evidence."""

    present: bool
    attestation_type: str | None = None
    provider: str | None = None
    status: str = "UNKNOWN"
    subject: str | None = None
    measurement: str | None = None
    model_digest: str | None = None
    environment_digest: str | None = None
    timestamp: str | None = None
    signature: str | None = None
    raw_evidence: Any | None = None
    claims: dict[str, Any] = field(default_factory=dict)
    verification_errors: list[str] = field(default_factory=list)
    source: str = "EXECUTION_ATTESTATION"

    @property
    def is_valid(self) -> bool:
        """Return whether the attestation is explicitly marked valid."""

        return (
            self.present
            and self.status.upper() == "VALID"
            and not self.verification_errors
        )

    @property
    def is_verified(self) -> bool:
        """Alias for is_valid."""

        return self.is_valid


def _normalize(value: Any) -> Any:
    """Convert common values into JSON-compatible structures."""

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Mapping):
        return {
            str(key): _normalize(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_normalize(item) for item in value]

    if isinstance(value, bytes):
        return value.hex()

    return str(value)


def _get_string(
    data: Mapping[str, Any],
    *keys: str,
) -> str | None:
    """Return the first non-empty value from the supplied keys."""

    for key in keys:
        value = data.get(key)

        if value is None:
            continue

        value = str(value).strip()

        if value:
            return value

    return None


def _validate_status(status: str) -> str:
    """Normalize an attestation status."""

    normalized = status.strip().upper()

    allowed = {
        "VALID",
        "INVALID",
        "UNVERIFIED",
        "UNKNOWN",
        "EXPIRED",
        "REVOKED",
        "PENDING",
    }

    return normalized if normalized in allowed else "UNKNOWN"


def create_attestation_evidence(
    evidence: Mapping[str, Any] | None,
) -> AttestationEvidence:
    """
    Create normalized attestation evidence from provider-supplied data.
    """

    if evidence is None:
        return AttestationEvidence(
            present=False,
            status="UNKNOWN",
        )

    if not isinstance(evidence, Mapping):
        raise InvalidAttestationError(
            "Attestation evidence must be a mapping/dictionary."
        )

    normalized = _normalize(evidence)

    if not isinstance(normalized, dict):
        raise InvalidAttestationError(
            "Unable to normalize attestation evidence."
        )

    present_value = normalized.get("present", True)

    if isinstance(present_value, str):
        present = present_value.strip().lower() in {
            "true",
            "yes",
            "1",
        }
    else:
        present = bool(present_value)

    status = _validate_status(
        _get_string(
            normalized,
            "status",
            "verification_status",
        )
        or "UNKNOWN"
    )

    errors_value = normalized.get(
        "verification_errors",
        normalized.get("errors", []),
    )

    if errors_value is None:
        verification_errors: list[str] = []
    elif isinstance(errors_value, list):
        verification_errors = [str(item) for item in errors_value]
    else:
        verification_errors = [str(errors_value)]

    claims_value = normalized.get("claims", {})

    claims = (
        claims_value
        if isinstance(claims_value, dict)
        else {"value": claims_value}
    )

    return AttestationEvidence(
        present=present,
        attestation_type=_get_string(
            normalized,
            "attestation_type",
            "type",
        ),
        provider=_get_string(
            normalized,
            "provider",
            "attestation_provider",
        ),
        status=status,
        subject=_get_string(
            normalized,
            "subject",
            "subject_id",
        ),
        measurement=_get_string(
            normalized,
            "measurement",
            "measurement_digest",
        ),
        model_digest=_get_string(
            normalized,
            "model_digest",
            "model_hash",
        ),
        environment_digest=_get_string(
            normalized,
            "environment_digest",
            "environment_hash",
        ),
        timestamp=_get_string(
            normalized,
            "timestamp",
            "attestation_time",
        ),
        signature=_get_string(
            normalized,
            "signature",
            "signature_value",
        ),
        raw_evidence=normalized.get(
            "raw_evidence",
            normalized,
        ),
        claims=claims,
        verification_errors=verification_errors,
    )


def validate_attestation(
    attestation: AttestationEvidence,
) -> list[str]:
    """Perform structural validation of attestation evidence."""

    if not isinstance(attestation, AttestationEvidence):
        raise InvalidAttestationError(
            "attestation must be an AttestationEvidence instance."
        )

    if not attestation.present:
        return []

    errors: list[str] = []

    if not attestation.attestation_type:
        errors.append("Attestation type is missing.")

    if not attestation.provider:
        errors.append("Attestation provider is missing.")

    if attestation.status == "UNKNOWN":
        errors.append(
            "Attestation verification status is unknown."
        )

    if (
        attestation.status == "VALID"
        and not attestation.signature
    ):
        errors.append(
            "Attestation is marked VALID but no signature "
            "evidence was supplied."
        )

    if (
        attestation.status == "VALID"
        and not (
            attestation.measurement
            or attestation.environment_digest
        )
    ):
        errors.append(
            "Attestation is marked VALID but no environment "
            "measurement or environment digest was supplied."
        )

    return errors


def verify_attestation(
    attestation: AttestationEvidence,
) -> AttestationEvidence:
    """
    Perform structural verification and return updated evidence.

    Provider-specific cryptographic verification belongs to the
    corresponding attestation provider adapter.
    """

    errors = validate_attestation(attestation)

    existing_errors = list(attestation.verification_errors)

    for error in errors:
        if error not in existing_errors:
            existing_errors.append(error)

    return AttestationEvidence(
        present=attestation.present,
        attestation_type=attestation.attestation_type,
        provider=attestation.provider,
        status=attestation.status,
        subject=attestation.subject,
        measurement=attestation.measurement,
        model_digest=attestation.model_digest,
        environment_digest=attestation.environment_digest,
        timestamp=attestation.timestamp,
        signature=attestation.signature,
        raw_evidence=attestation.raw_evidence,
        claims=dict(attestation.claims),
        verification_errors=existing_errors,
        source=attestation.source,
    )


def has_attestation(
    attestation: AttestationEvidence,
) -> bool:
    """Return whether attestation evidence is present."""

    if not isinstance(attestation, AttestationEvidence):
        raise InvalidAttestationError(
            "attestation must be an AttestationEvidence instance."
        )

    return attestation.present


def get_attestation_status(
    attestation: AttestationEvidence,
) -> str:
    """Return the normalized attestation status."""

    if not isinstance(attestation, AttestationEvidence):
        raise InvalidAttestationError(
            "attestation must be an AttestationEvidence instance."
        )

    return attestation.status


def attestation_to_dict(
    attestation: AttestationEvidence,
) -> dict[str, Any]:
    """Convert attestation evidence into a JSON-compatible dictionary."""

    if not isinstance(attestation, AttestationEvidence):
        raise InvalidAttestationError(
            "attestation must be an AttestationEvidence instance."
        )

    return {
        "present": attestation.present,
        "attestation_type": attestation.attestation_type,
        "provider": attestation.provider,
        "status": attestation.status,
        "subject": attestation.subject,
        "measurement": attestation.measurement,
        "model_digest": attestation.model_digest,
        "environment_digest": attestation.environment_digest,
        "timestamp": attestation.timestamp,
        "signature": attestation.signature,
        "raw_evidence": _normalize(
            attestation.raw_evidence
        ),
        "claims": _normalize(attestation.claims),
        "verification_errors": list(
            attestation.verification_errors
        ),
        "source": attestation.source,
        "is_valid": attestation.is_valid,
    }


__all__ = [
    "AttestationEvidence",
    "AttestationError",
    "InvalidAttestationError",
    "UnsupportedAttestationError",
    "AttestationVerificationError",
    "create_attestation_evidence",
    "validate_attestation",
    "verify_attestation",
    "has_attestation",
    "get_attestation_status",
    "attestation_to_dict",
]

