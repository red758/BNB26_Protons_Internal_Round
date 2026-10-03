```python
"""
ModelLedger Evidence - C2PA

C2PA provenance evidence collection and validation.

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

from dataclasses import dataclass, field
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
    """Raised when C2PA data cannot be read from an asset."""


@dataclass(frozen=True)
class C2PAEvidence:
    """
    C2PA evidence extracted from a digital asset.

    Attributes:
        present:
            Whether C2PA manifest information was found.

        validation_state:
            Validation state reported by the C2PA SDK.

        validation_results:
            Detailed validation results returned by the SDK.

        active_manifest:
            Active manifest returned by the SDK, when available.

        manifest_json:
            Manifest representation returned by the SDK, when available.

        source:
            Name of the evidence source.
    """

    present: bool
    validation_state: str | None
    validation_results: list[Any] = field(default_factory=list)
    active_manifest: dict[str, Any] | None = None
    manifest_json: Any | None = None
    source: str = "C2PA"


def _load_c2pa() -> Any:
    """
    Import the official C2PA Python SDK.

    The import is intentionally lazy so the rest of the ModelLedger
    evidence package can still be imported when C2PA support has not
    been installed.
    """

    try:
        import c2pa
    except ImportError as exc:
        raise C2PANotInstalledError(
            "c2pa-python is not installed. "
            "Install it with: python -m pip install c2pa-python"
        ) from exc

    return c2pa


def _validate_asset(path: str | Path) -> Path:
    """
    Validate and normalize an asset path.
    """

    asset_path = Path(path)

    if not asset_path.exists():
        raise C2PAFileNotFoundError(
            f"Asset does not exist: {asset_path}"
        )

    if not asset_path.is_file():
        raise InvalidC2PAFileError(
            f"Asset path is not a regular file: {asset_path}"
        )

    return asset_path


def _call_sdk_method(
    obj: Any,
    method_name: str,
    default: Any = None,
) -> Any:
    """
    Safely call an SDK method.

    This keeps the adapter defensive against SDK versions where
    optional methods may not be available.
    """

    method = getattr(obj, method_name, None)

    if method is None or not callable(method):
        return default

    try:
        return method()
    except Exception:
        return default


def _normalize(value: Any) -> Any:
    """
    Convert common SDK values into JSON-compatible structures.

    No evidence is fabricated. Unknown SDK objects are represented
    using their string representation.
    """

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {
            str(key): _normalize(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]

    return str(value)


def _normalize_dict(value: Any) -> dict[str, Any] | None:
    """Normalize dictionary-like SDK output."""

    normalized = _normalize(value)

    if isinstance(normalized, dict):
        return normalized

    return None


def _normalize_list(value: Any) -> list[Any]:
    """Normalize list-like SDK output."""

    normalized = _normalize(value)

    if normalized is None:
        return []

    if isinstance(normalized, list):
        return normalized

    return [normalized]


def read_c2pa(path: str | Path) -> C2PAEvidence:
    """
    Read C2PA provenance information from an asset.

    The official c2pa-python SDK is responsible for reading and
    validating the C2PA manifest.

    Args:
        path:
            Path to the digital asset.

    Returns:
        C2PAEvidence containing the C2PA evidence exposed by the SDK.

    Raises:
        C2PANotInstalledError:
            If c2pa-python is not installed.

        C2PAFileNotFoundError:
            If the asset does not exist.

        InvalidC2PAFileError:
            If the path is not a regular file.

        C2PAReadError:
            If the C2PA SDK cannot process the asset.
    """

    asset_path = _validate_asset(path)
    c2pa = _load_c2pa()

    try:
        reader = c2pa.Reader(str(asset_path))
    except Exception as exc:
        raise C2PAReadError(
            f"Unable to read C2PA data from '{asset_path}': {exc}"
        ) from exc

    validation_state = _call_sdk_method(
        reader,
        "get_validation_state",
    )

    validation_results = _call_sdk_method(
        reader,
        "get_validation_results",
        [],
    )

    active_manifest = _call_sdk_method(
        reader,
        "get_active_manifest",
    )

    manifest_json = _call_sdk_method(
        reader,
        "json",
    )

    normalized_state = _normalize(validation_state)

    if normalized_state is not None:
        normalized_state = str(normalized_state)

    normalized_manifest = _normalize_dict(active_manifest)

    normalized_results = _normalize_list(validation_results)

    normalized_json = _normalize(manifest_json)

    present = (
        normalized_manifest is not None
        or normalized_json is not None
    )

    return C2PAEvidence(
        present=present,
        validation_state=normalized_state,
        validation_results=normalized_results,
        active_manifest=normalized_manifest,
        manifest_json=normalized_json,
    )


def has_c2pa(path: str | Path) -> bool:
    """
    Check whether an asset exposes readable C2PA manifest data.

    This function does not determine whether the asset is authentic.
    """

    evidence = read_c2pa(path)
    return evidence.present


def get_c2pa_validation_state(path: str | Path) -> str | None:
    """
    Return the C2PA validation state for an asset.

    Returns None when the SDK does not expose a validation state.
    """

    evidence = read_c2pa(path)
    return evidence.validation_state


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
```

### Your current structure

```text
evidence/
├── __init__.py
├── hash.py
├── metadata.py
└── c2pa.py
```

After pasting, **save and commit only this change**.

One important thing: don't add fake C2PA data or hardcode a `VALID` result. `c2pa.py` must report what the actual C2PA SDK finds in the actual asset.

