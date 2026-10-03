"""
ModelLedger Evidence - C2PA

C2PA provenance evidence collection.

This module uses the official c2pa-python package to read C2PA
manifests from digital assets, and extracts the fields ModelLedger
cares about: manifest, validation, signer, creator, generator/model,
dates, and AI actions.

This module ONLY collects C2PA evidence.

It does NOT:
- decide whether content is authentic
- decide whether content was AI-generated
- assign a trust score
- produce the final ModelLedger verdict

Notes on what the extracted fields mean:
- `creators` are SELF-DECLARED in the manifest (schema.org author).
  The SDK does not verify them.
- `signer` is the identity on the signing certificate, which is not
  the same thing as the creator.
- A validation_state of "Valid" can coexist with an untrusted signing
  credential. Both facts are reported; see `signing_credential_trusted`.
- `ai_related` on an action only means its declared IPTC
  digitalSourceType is in AI_SOURCE_TYPES. Note that `algorithmicMedia`
  means algorithmically generated, not necessarily a trained model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# IPTC digitalSourceType terms (lowercased) treated as AI / algorithmic.
AI_SOURCE_TYPES = frozenset(
    {
        "trainedalgorithmicmedia",
        "compositewithtrainedalgorithmicmedia",
        "algorithmicmedia",
    }
)


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
class C2PAIssue:
    """A validation failure reported by the SDK."""

    code: str
    explanation: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class C2PASigner:
    """Signing certificate details from the active manifest."""

    issuer: str | None = None
    common_name: str | None = None
    algorithm: str | None = None
    serial_number: str | None = None
    signed_at: str | None = None  # only present when a timestamp authority was used


@dataclass(frozen=True)
class C2PACreator:
    """A self-declared author from the manifest (unverified)."""

    name: str
    type: str | None = None
    source: str = "stds.schema-org.CreativeWork"


@dataclass(frozen=True)
class C2PAGenerator:
    """
    Software named in the manifest.

    role: "claim_generator" (the app that made the claim) or
          "software_agent" (the tool named on an action).
    """

    name: str
    version: str | None = None
    role: str = "claim_generator"
    manifest_label: str | None = None


@dataclass(frozen=True)
class C2PAAction:
    """One action from a c2pa.actions assertion."""

    action: str
    manifest_label: str | None = None
    in_active_manifest: bool = False
    digital_source_type: str | None = None  # term, e.g. "trainedAlgorithmicMedia"
    digital_source_type_uri: str | None = None
    ai_related: bool = False
    software_agent: str | None = None
    software_agent_version: str | None = None
    when: str | None = None


@dataclass(frozen=True)
class C2PAEvidence:
    """
    C2PA evidence extracted from a digital asset.

    Attributes:
        present:
            True if a C2PA manifest was found. False means the SDK
            looked and found none (NOT an error, and NOT a statement
            about authenticity).

        validation_state:
            State reported by the SDK ("Valid", "Invalid", "Trusted").

        validation_results:
            Raw detailed validation results from the SDK.

        active_manifest / manifest_json:
            Raw active manifest and full manifest store.

        source:
            Name of the evidence source.

        manifest_label:
            Label (id) of the active manifest.

        validation_failures:
            Failure entries the SDK reported for the active manifest.
            Can be non-empty even when validation_state is "Valid"
            (e.g. signingCredential.untrusted).

        signing_credential_trusted:
            True/False if the SDK reported a trust result for the
            signing credential, None if it reported neither.

        signer:
            Signing certificate details.

        creators:
            Self-declared authors (unverified).

        generators:
            Claim generators and per-action software agents.

        actions:
            Every action across ALL manifests in the store (so edits
            of earlier AI-made content are visible), each tagged with
            whether it came from the active manifest.
    """

    present: bool
    validation_state: str | None = None
    validation_results: Any | None = None
    active_manifest: dict[str, Any] | None = None
    manifest_json: Any | None = None
    source: str = "C2PA"
    manifest_label: str | None = None
    validation_failures: list[C2PAIssue] = field(default_factory=list)
    signing_credential_trusted: bool | None = None
    signer: C2PASigner | None = None
    creators: list[C2PACreator] = field(default_factory=list)
    generators: list[C2PAGenerator] = field(default_factory=list)
    actions: list[C2PAAction] = field(default_factory=list)

    @property
    def ai_actions(self) -> list[C2PAAction]:
        """Actions whose declared digitalSourceType is AI-related."""
        return [a for a in self.actions if a.ai_related]

    @property
    def has_ai_action(self) -> bool:
        return any(a.ai_related for a in self.actions)


# --------------------------------------------------------------------- #
# SDK plumbing
# --------------------------------------------------------------------- #


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
    asset_path = Path(path)

    if not asset_path.exists():
        raise C2PAFileNotFoundError(f"Asset does not exist: {asset_path}")

    if not asset_path.is_file():
        raise InvalidC2PAFileError(
            f"Asset path is not a regular file: {asset_path}"
        )

    return asset_path


def _is_manifest_not_found(exc: Exception) -> bool:
    """True when the SDK says "no C2PA data here" (a normal outcome)."""

    return "ManifestNotFound" in type(exc).__name__ or str(exc).startswith(
        "ManifestNotFound"
    )


def _normalize(value: Any) -> Any:
    """Convert SDK values into JSON-compatible structures."""

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


# --------------------------------------------------------------------- #
# field extraction (pure functions over normalized dicts)
# --------------------------------------------------------------------- #


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _manifest_store(
    manifest_json: Any,
    active_manifest: dict[str, Any] | None,
) -> tuple[str | None, dict[str, dict[str, Any]], dict[str, Any] | None]:
    """Return (active label, {label: manifest}, active manifest)."""

    store: dict[str, dict[str, Any]] = {}
    label: str | None = None

    if isinstance(manifest_json, dict):
        manifests = manifest_json.get("manifests")
        if isinstance(manifests, dict):
            store = {
                str(k): v for k, v in manifests.items() if isinstance(v, dict)
            }
        label = _text(manifest_json.get("active_manifest"))

    if label is None and active_manifest:
        label = _text(active_manifest.get("label"))

    active = store.get(label) if label else None
    if active is None:
        active = active_manifest

    if active is not None and label and label not in store:
        store[label] = active

    return label, store, active


def _assertions(manifest: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    out = []
    for assertion in _as_list(manifest.get("assertions")):
        if isinstance(assertion, dict):
            label = assertion.get("label")
            if isinstance(label, str) and label.startswith(prefix):
                data = assertion.get("data")
                if isinstance(data, dict):
                    out.append(data)
    return out


def _agent(value: Any) -> tuple[str | None, str | None]:
    """softwareAgent may be a string or {name, version}."""
    if isinstance(value, dict):
        return _text(value.get("name")), _text(value.get("version"))
    return _text(value), None


def _extract_signer(manifest: dict[str, Any] | None) -> C2PASigner | None:
    info = (manifest or {}).get("signature_info")
    if not isinstance(info, dict):
        return None

    return C2PASigner(
        issuer=_text(info.get("issuer")),
        common_name=_text(info.get("common_name")),
        algorithm=_text(info.get("alg")),
        serial_number=_text(info.get("cert_serial_number")),
        signed_at=_text(info.get("time")),
    )


def _extract_creators(manifest: dict[str, Any] | None) -> list[C2PACreator]:
    creators: list[C2PACreator] = []

    for data in _assertions(manifest or {}, "stds.schema-org.CreativeWork"):
        for author in _as_list(data.get("author")):
            if isinstance(author, dict):
                name = _text(author.get("name"))
                kind = _text(author.get("@type"))
            else:
                name, kind = _text(author), None
            if name:
                creators.append(C2PACreator(name=name, type=kind))

    return list(dict.fromkeys(creators))


def _extract_actions(
    store: dict[str, dict[str, Any]],
    active_label: str | None,
) -> list[C2PAAction]:
    actions: list[C2PAAction] = []

    for label, manifest in store.items():
        for data in _assertions(manifest, "c2pa.actions"):
            for raw in _as_list(data.get("actions")):
                if not isinstance(raw, dict):
                    continue
                name = _text(raw.get("action"))
                if not name:
                    continue

                uri = _text(raw.get("digitalSourceType"))
                term = uri.rstrip("/").rsplit("/", 1)[-1] if uri else None
                agent, agent_version = _agent(raw.get("softwareAgent"))

                actions.append(
                    C2PAAction(
                        action=name,
                        manifest_label=label,
                        in_active_manifest=(label == active_label),
                        digital_source_type=term,
                        digital_source_type_uri=uri,
                        ai_related=bool(
                            term and term.lower() in AI_SOURCE_TYPES
                        ),
                        software_agent=agent,
                        software_agent_version=agent_version,
                        when=_text(raw.get("when")),
                    )
                )

    return actions


def _extract_generators(
    active: dict[str, Any] | None,
    active_label: str | None,
    actions: list[C2PAAction],
) -> list[C2PAGenerator]:
    generators: list[C2PAGenerator] = []

    if active:
        legacy = _text(active.get("claim_generator"))
        if legacy:
            generators.append(
                C2PAGenerator(name=legacy, manifest_label=active_label)
            )

        for info in _as_list(active.get("claim_generator_info")):
            if isinstance(info, dict) and _text(info.get("name")):
                generators.append(
                    C2PAGenerator(
                        name=_text(info.get("name")),  # type: ignore[arg-type]
                        version=_text(info.get("version")),
                        manifest_label=active_label,
                    )
                )

    for action in actions:
        if action.software_agent:
            generators.append(
                C2PAGenerator(
                    name=action.software_agent,
                    version=action.software_agent_version,
                    role="software_agent",
                    manifest_label=action.manifest_label,
                )
            )

    return list(dict.fromkeys(generators))


def _issues(entries: Any) -> list[C2PAIssue]:
    issues = []
    for entry in _as_list(entries):
        if isinstance(entry, dict) and _text(entry.get("code")):
            issues.append(
                C2PAIssue(
                    code=entry["code"],
                    explanation=_text(entry.get("explanation")),
                    url=_text(entry.get("url")),
                )
            )
    return issues


def _extract_validation(
    results: Any,
    manifest_json: Any,
) -> tuple[list[C2PAIssue], bool | None]:
    """Return (failures, signing_credential_trusted) for the active manifest."""

    active = results.get("activeManifest") if isinstance(results, dict) else None
    active = active if isinstance(active, dict) else {}

    failures = _issues(active.get("failure"))

    if not failures and not active and isinstance(manifest_json, dict):
        failures = _issues(manifest_json.get("validation_status"))

    trusted: bool | None = None
    all_codes = {
        i.code
        for key in ("success", "informational", "failure")
        for i in _issues(active.get(key))
    } | {f.code for f in failures}

    if "signingCredential.untrusted" in all_codes:
        trusted = False
    elif "signingCredential.trusted" in all_codes:
        trusted = True

    return failures, trusted


# --------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------- #


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
            active_raw = reader.get_active_manifest()
            json_raw = reader.json()
        except Exception as exc:
            raise C2PAReadError(
                f"C2PA manifest found in '{asset_path}' but could not be "
                f"fully read: {exc}"
            ) from exc
    finally:
        close = getattr(reader, "close", None)
        if callable(close):
            close()

    results_n = _normalize(results)
    active_n = _normalize(active_raw)
    active_n = active_n if isinstance(active_n, dict) else None
    json_n = _parse_json(json_raw)

    label, store, active = _manifest_store(json_n, active_n)
    actions = _extract_actions(store, label)
    failures, trusted = _extract_validation(results_n, json_n)

    return C2PAEvidence(
        present=True,
        validation_state=None if state is None else str(_normalize(state)),
        validation_results=results_n,
        active_manifest=active_n,
        manifest_json=json_n,
        manifest_label=label,
        validation_failures=failures,
        signing_credential_trusted=trusted,
        signer=_extract_signer(active),
        creators=_extract_creators(active),
        generators=_extract_generators(active, label, actions),
        actions=actions,
    )


def has_c2pa(path: str | Path) -> bool:
    """Check whether an asset contains C2PA manifest data."""

    return read_c2pa(path).present


def get_c2pa_validation_state(path: str | Path) -> str | None:
    """Return the SDK's validation state, or None if no manifest."""

    return read_c2pa(path).validation_state


__all__ = [
    "AI_SOURCE_TYPES",
    "C2PAAction",
    "C2PACreator",
    "C2PAError",
    "C2PAEvidence",
    "C2PAFileNotFoundError",
    "C2PAGenerator",
    "C2PAIssue",
    "C2PANotInstalledError",
    "C2PAReadError",
    "C2PASigner",
    "InvalidC2PAFileError",
    "get_c2pa_validation_state",
    "has_c2pa",
    "read_c2pa",
]
