"""
ModelLedger Evidence - C2PA

C2PA provenance evidence collection.

This module uses the official c2pa-python package to read C2PA
manifests from digital assets.

This module ONLY collects C2PA evidence.

It does NOT:
- decide whether content is authentic
- decide whether content was AI-generated
- assign a trust score
- produce the final ModelLedger verdict

Those decisions belong to the Evidence Engine / Trust Policy layer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class C2PAError(Exception):
    """Base exception for C2PA-related errors."""


class C2PANotInstalledError(C2PAError):
    """Raised when c2pa-python is not installed."""


class C2PAFileNotFoundError(C2PAError):
    """Raised when the asset does not exist."""


class InvalidC2PAFileError(C2PAError):
    """Raised when the supplied path is not a regular file."""


class C2PAReadError(C2PAError):
    """Raised when the SDK fails to process an asset (corrupt/unsupported)."""


@dataclass(frozen=True)
class C2PAEvidence:
    """
    C2PA evidence extracted from a digital asset.

    Attributes:
        present:
            True if a C2PA manifest was found. False means the SDK
            looked and found none (this is NOT an error, and NOT a
            statement about authenticity).

        validation_state:
            Validation state reported by the SDK (None if no manifest).

        validation_results:
            Detailed validation results from the SDK, as returned
            (dict in current SDK versions). None if unavailable.

        active_manifest:
            Active manifest returned by the SDK, when available.

        manifest_json:
            Full manifest store, parsed from the SDK's JSON output.

        source:
            Name of the evidence source.
    """

    present: bool
    validation_state: str | None = None
    validation_results: Any | None = None
    active_manifest: dict[str, Any] | None = None
    manifest_json: Any | None = None
    source: str = "C2PA"


def _load_c2pa() -> Any:
    """Lazily import the official C2PA Python SDK."""

    try:
        import c2pa
    except ImportError as exc:
        raise C2PANotInstalledError(
            "c2pa-python is not installed. "
            "Install it with: python -m pip install c2pa-python"
        ) from exc

    return c2pa


def _validate_asset(path: str | Path) -> Path:
    """Validate and normalize an asset path."""

    asset_path = Path(path)

    if not asset_path.exists():
        raise C2PAFileNotFoundError(f"Asset does not exist: {asset_path}")

    if not asset_path.is_file():
        raise InvalidC2PAFileError(
            f"Asset path is not a regular file: {asset_path}"
        )

    return asset_path


def _is_manifest_not_found(exc: Exception) -> bool:
    """
    True when the SDK is saying "this asset has no C2PA data".

    That is a normal outcome (most files are unsigned), not a failure.
    """

    return "ManifestNotFound" in type(exc).__name__ or str(exc).startswith(
        "ManifestNotFound"
    )


def _normalize(value: Any) -> Any:
    """
    Convert SDK values into JSON-compatible structures.

    No evidence is fabricated. Unknown SDK objects are represented
    using their string representation.
    """

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]

    return str(value)


def _parse_json(value: Any) -> Any:
    """Parse the SDK's JSON string; fall back to the raw value."""

    if isinstance(value, (str, bytes)):
        try:
            return json.loads(value)
        except ValueError:
            return _normalize(value)

    return _normalize(value)


def read_c2pa(path: str | Path) -> C2PAEvidence:
    """
    Read C2PA provenance information from an asset.

    Returns:
        C2PAEvidence. If the asset has no manifest, `present` is False
        and every other field is empty. That is not an error.

    Raises:
        C2PANotInstalledError: c2pa-python is not installed.
        C2PAFileNotFoundError: the asset does not exist.
        InvalidC2PAFileError: the path is not a regular file.
        C2PAReadError: the SDK failed on the asset (corrupt, unsupported
            format, malformed manifest, etc.).
    """

    asset_path = _validate_asset(path)
    c2pa = _load_c2pa()

    try:
        reader = c2pa.Reader(str(asset_path))
    except Exception as exc:
        if _is_manifest_not_found(exc):
            return C2PAEvidence(present=False)
        raise C2PAReadError(
            f"Unable to read C2PA data from '{asset_path}': {exc}"
        ) from exc

    try:
        try:
            state = reader.get_validation_state()
            results = reader.get_validation_results()
            active = reader.get_active_manifest()
            raw_json = reader.json()
        except Exception as exc:
            # A manifest exists but the SDK choked reading it. Surface
            # that instead of silently returning empty evidence.
            raise C2PAReadError(
                f"C2PA manifest found in '{asset_path}' but could not be "
                f"fully read: {exc}"
            ) from exc
    finally:
        close = getattr(reader, "close", None)
        if callable(close):
            close()

    manifest = _normalize(active)

    return C2PAEvidence(
        present=True,
        validation_state=None if state is None else str(_normalize(state)),
        validation_results=_normalize(results),
        active_manifest=manifest if isinstance(manifest, dict) else None,
        manifest_json=_parse_json(raw_json),
    )


def has_c2pa(path: str | Path) -> bool:
    """
    Check whether an asset contains C2PA manifest data.

    Does not determine whether the asset is authentic.
    """

    return read_c2pa(path).present


def get_c2pa_validation_state(path: str | Path) -> str | None:
    """Return the SDK's validation state, or None if no manifest."""

    return read_c2pa(path).validation_state


__all__ = [
    "C2PAEvidence",
    "C2PAError",
    "C2PANotInstalledError",
    "C2PAFileNotFoundError",
    "InvalidC2PAFileError",
    "C2PAReadError",
    "read_c2pa",
    "has_c2pa",
    "get_c2pa_validation_state",
]