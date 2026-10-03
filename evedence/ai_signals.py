
"""
ModelLedger Evidence - AI Signals

Collects AI-generation signals that are *embedded in or declared by* a
digital asset:

- PNG text chunks written by common generators (Stable Diffusion /
  A1111 "parameters", ComfyUI "prompt"/"workflow", InvokeAI, NovelAI)
- IPTC DigitalSourceType values found in XMP
- DigitalSourceType and claim generator values found in a C2PA manifest
- Known generator names appearing in the text fields above

This module ONLY collects signals.

It does NOT:
- decide whether content is AI-generated
- decide whether content is authentic
- assign a trust score
- produce the final ModelLedger verdict

IMPORTANT: absence of signals is NOT evidence that content is not
AI-generated. Metadata is trivially stripped. Interpretation belongs
to the Evidence Engine / Trust Policy layer.
"""

from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Max bytes read from the head of a file when scanning for XMP.
_XMP_SCAN_LIMIT = 16 * 1024 * 1024
# Max decompressed size accepted for a compressed PNG text chunk.
_PNG_TEXT_LIMIT = 1024 * 1024
# Max characters of a value kept in a signal.
_PREVIEW_CHARS = 200

# PNG text keys that generators are known to write.
_GENERATOR_PNG_KEYS = {
    "parameters": "Stable Diffusion / A1111-style parameters",
    "prompt": "ComfyUI-style prompt graph",
    "workflow": "ComfyUI-style workflow",
    "invokeai_metadata": "InvokeAI metadata",
    "invokeai_graph": "InvokeAI graph",
    "sd-metadata": "Stable Diffusion metadata",
    "dream": "Stable Diffusion (dream) metadata",
}

# IPTC DigitalSourceType terms that denote AI / algorithmic origin.
_AI_SOURCE_TERMS = {
    "trainedalgorithmicmedia",
    "compositewithtrainedalgorithmicmedia",
    "algorithmicmedia",
}

# Generator names, matched on word boundaries, case-insensitive.
_GENERATOR_KEYWORDS = [
    "midjourney",
    "dall-e",
    "dalle",
    "stable diffusion",
    "stablediffusion",
    "comfyui",
    "automatic1111",
    "invokeai",
    "novelai",
    "adobe firefly",
    "firefly",
    "leonardo.ai",
    "ideogram",
    "imagen",
    "gemini",
    "openai",
    "sora",
    "runway",
    "flux",
]
_KEYWORD_RE = re.compile(
    r"(?<![A-Za-z0-9])(" + "|".join(re.escape(k) for k in _GENERATOR_KEYWORDS) + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)

_XMP_BLOCK_RE = re.compile(rb"<x:xmpmeta.*?</x:xmpmeta>", re.DOTALL)
_DST_PATTERNS = [
    re.compile(r"DigitalSourceType\s*=\s*[\"']([^\"']+)[\"']"),
    re.compile(r"DigitalSourceType[^>]*?rdf:resource\s*=\s*[\"']([^\"']+)[\"']"),
    re.compile(r"DigitalSourceType\s*>\s*([^<]+?)\s*<"),
]


class AISignalsError(Exception):
    """Base exception for AI-signal collection errors."""


class AISignalsFileNotFoundError(AISignalsError):
    """Raised when the asset does not exist."""


class InvalidAISignalsFileError(AISignalsError):
    """Raised when the supplied path is not a regular file."""


class AISignalsReadError(AISignalsError):
    """Raised when the asset cannot be read from disk."""


@dataclass(frozen=True)
class AISignal:
    """
    A single observed signal.

    Attributes:
        kind:
            "digital_source_type"  - IPTC DigitalSourceType value
            "generator_parameters" - generator-specific PNG text key
            "generator_keyword"    - known generator name in a text field
            "claim_generator"      - C2PA claim generator name

        source:
            Where it was observed: "png_text", "xmp", or "c2pa".

        value:
            The observed value (truncated to a short preview).

        detail:
            Extra context, e.g. the PNG key or whether a
            DigitalSourceType term is AI-related per IPTC.
    """

    kind: str
    source: str
    value: str
    detail: str | None = None


@dataclass(frozen=True)
class AISignalEvidence:
    """
    AI signals collected from an asset.

    Attributes:
        signals:
            Every signal observed. Empty does NOT mean "not AI".

        checked:
            Which sources were actually inspected, so downstream logic
            can tell "looked and found nothing" from "never looked".

        source:
            Name of the evidence source.
    """

    signals: list[AISignal] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)
    source: str = "AI_SIGNALS"

    @property
    def found(self) -> bool:
        return bool(self.signals)


# --------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------- #


def _validate_asset(path: str | Path) -> Path:
    asset_path = Path(path)

    if not asset_path.exists():
        raise AISignalsFileNotFoundError(f"Asset does not exist: {asset_path}")

    if not asset_path.is_file():
        raise InvalidAISignalsFileError(
            f"Asset path is not a regular file: {asset_path}"
        )

    return asset_path


def _preview(text: str) -> str:
    text = text.strip()
    if len(text) > _PREVIEW_CHARS:
        return text[:_PREVIEW_CHARS] + "..."
    return text


def _term(value: str) -> str:
    """'http://cv.iptc.org/newscodes/digitalsourcetype/X' -> 'X'."""
    return value.strip().rstrip("/").rsplit("/", 1)[-1]


def _digital_source_signal(value: str, source: str) -> AISignal:
    term = _term(value)
    ai_related = term.lower() in _AI_SOURCE_TERMS
    return AISignal(
        kind="digital_source_type",
        source=source,
        value=term,
        detail="ai_related=true" if ai_related else "ai_related=false",
    )


def _keyword_signals(text: str, source: str) -> list[AISignal]:
    seen: set[str] = set()
    out: list[AISignal] = []

    for match in _KEYWORD_RE.finditer(text):
        keyword = match.group(1).lower()
        if keyword in seen:
            continue
        seen.add(keyword)
        start = max(0, match.start() - 30)
        snippet = text[start : match.end() + 30].replace("\n", " ")
        out.append(
            AISignal(
                kind="generator_keyword",
                source=source,
                value=keyword,
                detail=_preview(snippet),
            )
        )

    return out


# --------------------------------------------------------------------- #
# PNG text chunks
# --------------------------------------------------------------------- #


def _inflate(data: bytes) -> str:
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(data, _PNG_TEXT_LIMIT)
    return raw.decode("utf-8", errors="replace")


def _parse_text_chunk(chunk_type: bytes, data: bytes) -> tuple[str, str] | None:
    try:
        if chunk_type == b"tEXt":
            key, _, value = data.partition(b"\x00")
            return key.decode("latin-1"), value.decode("latin-1")

        if chunk_type == b"zTXt":
            key, _, rest = data.partition(b"\x00")
            return key.decode("latin-1"), _inflate(rest[1:])

        if chunk_type == b"iTXt":
            key, _, rest = data.partition(b"\x00")
            compressed, rest = rest[0], rest[2:]
            _lang, _, rest = rest.partition(b"\x00")
            _translated, _, text = rest.partition(b"\x00")
            value = _inflate(text) if compressed else text.decode("utf-8", "replace")
            return key.decode("utf-8", "replace"), value
    except (zlib.error, IndexError, UnicodeDecodeError):
        return None

    return None


def _png_text_entries(asset_path: Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    size = asset_path.stat().st_size

    with asset_path.open("rb") as handle:
        if handle.read(8) != PNG_SIGNATURE:
            return entries

        while True:
            header = handle.read(8)
            if len(header) < 8:
                break

            length, chunk_type = struct.unpack(">I4s", header)

            if length > size:
                break

            if chunk_type in (b"tEXt", b"zTXt", b"iTXt"):
                parsed = _parse_text_chunk(chunk_type, handle.read(length))
                if parsed is not None:
                    entries.append(parsed)
                handle.seek(4, 1)  # CRC
            else:
                handle.seek(length + 4, 1)

            if chunk_type == b"IEND":
                break

    return entries


def _collect_png(asset_path: Path) -> list[AISignal]:
    signals: list[AISignal] = []

    for key, value in _png_text_entries(asset_path):
        generator = _GENERATOR_PNG_KEYS.get(key.lower())

        if generator is not None:
            signals.append(
                AISignal(
                    kind="generator_parameters",
                    source="png_text",
                    value=_preview(value),
                    detail=f"key={key} ({generator})",
                )
            )

        signals.extend(_keyword_signals(f"{key}: {value}", "png_text"))

    return signals


# --------------------------------------------------------------------- #
# XMP
# --------------------------------------------------------------------- #


def _collect_xmp(asset_path: Path) -> list[AISignal]:
    signals: list[AISignal] = []

    with asset_path.open("rb") as handle:
        head = handle.read(_XMP_SCAN_LIMIT)

    for block in _XMP_BLOCK_RE.findall(head):
        text = block.decode("utf-8", errors="replace")

        for pattern in _DST_PATTERNS:
            for value in pattern.findall(text):
                signals.append(_digital_source_signal(value, "xmp"))

        signals.extend(_keyword_signals(text, "xmp"))

    return signals


# --------------------------------------------------------------------- #
# C2PA (read from evidence already collected by evidence.c2pa)
# --------------------------------------------------------------------- #


def _walk(node: Any):
    """Yield (key, value) for every dict entry in a nested structure."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _collect_c2pa(c2pa_evidence: Any) -> list[AISignal]:
    signals: list[AISignal] = []

    if c2pa_evidence is None or not getattr(c2pa_evidence, "present", False):
        return signals

    for tree in (
        getattr(c2pa_evidence, "active_manifest", None),
        getattr(c2pa_evidence, "manifest_json", None),
    ):
        for key, value in _walk(tree):
            if key == "digitalSourceType" and isinstance(value, str):
                signals.append(_digital_source_signal(value, "c2pa"))

            elif key == "claim_generator" and isinstance(value, str):
                signals.append(
                    AISignal("claim_generator", "c2pa", _preview(value))
                )
                signals.extend(_keyword_signals(value, "c2pa"))

            elif key == "claim_generator_info":
                infos = value if isinstance(value, list) else [value]
                for info in infos:
                    name = info.get("name") if isinstance(info, dict) else None
                    if isinstance(name, str):
                        signals.append(
                            AISignal("claim_generator", "c2pa", _preview(name))
                        )
                        signals.extend(_keyword_signals(name, "c2pa"))

    return signals


# --------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------- #


def collect_ai_signals(
    path: str | Path,
    c2pa_evidence: Any | None = None,
) -> AISignalEvidence:
    """
    Collect AI-generation signals from an asset.

    Args:
        path:
            Path to the digital asset.

        c2pa_evidence:
            Optional C2PAEvidence from evidence.c2pa.read_c2pa().
            Passing it avoids reading the manifest twice. When omitted,
            C2PA is simply not inspected (and not listed in `checked`).

    Returns:
        AISignalEvidence. `found` is False when nothing was observed,
        which says nothing about whether the asset is AI-generated.

    Raises:
        AISignalsFileNotFoundError: the asset does not exist.
        InvalidAISignalsFileError: the path is not a regular file.
        AISignalsReadError: the file could not be read.
    """

    asset_path = _validate_asset(path)

    signals: list[AISignal] = []
    checked: list[str] = []

    try:
        checked.append("xmp")
        signals.extend(_collect_xmp(asset_path))

        if asset_path.suffix.lower() == ".png":
            checked.append("png_text")
            signals.extend(_collect_png(asset_path))
    except OSError as exc:
        raise AISignalsReadError(
            f"Unable to read asset '{asset_path}': {exc}"
        ) from exc

    if c2pa_evidence is not None:
        checked.append("c2pa")
        signals.extend(_collect_c2pa(c2pa_evidence))

    unique = list(dict.fromkeys(signals))

    return AISignalEvidence(signals=unique, checked=checked)


def has_ai_signals(
    path: str | Path,
    c2pa_evidence: Any | None = None,
) -> bool:
    """
    True if any AI-related signal was observed.

    False does NOT mean the asset is not AI-generated.
    """

    return collect_ai_signals(path, c2pa_evidence).found


__all__ = [
    "AISignal",
    "AISignalEvidence",
    "AISignalsError",
    "AISignalsFileNotFoundError",
    "InvalidAISignalsFileError",
    "AISignalsReadError",
    "collect_ai_signals",
    "has_ai_signals",
]