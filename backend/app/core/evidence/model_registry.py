
"""
ModelLedger Evidence - Model Registry

A static registry of known AI generators, services, and tools, used to
turn names observed in an asset's metadata into canonical entries.

This module ONLY resolves names.

It does NOT:
- decide whether content is AI-generated
- decide which model produced an asset
- assign a trust score
- produce the final ModelLedger verdict

A match means a known NAME appeared in a signal. Nothing more. The
registry is also incomplete by nature; a miss means "not in registry".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

KIND_MODEL = "model"
KIND_SERVICE = "service"
KIND_TOOL = "tool"
KIND_VENDOR = "vendor"


@dataclass(frozen=True)
class ModelEntry:
    """A known generator, service, tool, or vendor."""

    model_id: str
    name: str
    kind: str
    vendor: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelMatch:
    """A registry entry matched against an observed signal."""

    model_id: str
    name: str
    kind: str
    vendor: str | None
    matched_alias: str
    signal_kind: str
    signal_source: str


DEFAULT_ENTRIES: tuple[ModelEntry, ...] = (
    ModelEntry("midjourney", "Midjourney", KIND_SERVICE, "Midjourney", ("midjourney",)),
    ModelEntry("dall-e", "DALL-E", KIND_MODEL, "OpenAI", ("dall-e", "dalle")),
    ModelEntry("sora", "Sora", KIND_MODEL, "OpenAI", ("sora",)),
    ModelEntry("chatgpt", "ChatGPT", KIND_SERVICE, "OpenAI", ("chatgpt",)),
    ModelEntry("openai", "OpenAI (product unspecified)", KIND_VENDOR, "OpenAI", ("openai",)),
    ModelEntry(
        "stable-diffusion", "Stable Diffusion", KIND_MODEL, "Stability AI",
        ("stable diffusion", "stablediffusion"),
    ),
    ModelEntry("adobe-firefly", "Adobe Firefly", KIND_MODEL, "Adobe", ("adobe firefly", "firefly")),
    ModelEntry("imagen", "Imagen", KIND_MODEL, "Google", ("imagen",)),
    ModelEntry("gemini", "Gemini", KIND_MODEL, "Google", ("gemini",)),
    ModelEntry("flux", "FLUX", KIND_MODEL, "Black Forest Labs", ("flux",)),
    ModelEntry("ideogram", "Ideogram", KIND_SERVICE, "Ideogram", ("ideogram",)),
    ModelEntry("leonardo-ai", "Leonardo.Ai", KIND_SERVICE, "Leonardo.Ai", ("leonardo.ai",)),
    ModelEntry("runway", "Runway", KIND_SERVICE, "Runway", ("runway",)),
    ModelEntry("novelai", "NovelAI", KIND_SERVICE, "Anlatan", ("novelai",)),
    ModelEntry("comfyui", "ComfyUI", KIND_TOOL, None, ("comfyui",)),
    ModelEntry("automatic1111", "AUTOMATIC1111 Web UI", KIND_TOOL, None, ("automatic1111",)),
    ModelEntry("invokeai", "InvokeAI", KIND_TOOL, None, ("invokeai",)),
)

# Signal kinds whose value is a name worth resolving.
_RESOLVABLE_SIGNAL_KINDS = {"generator_keyword", "claim_generator"}


class ModelRegistry:
    """Name -> entry lookup with word-boundary, case-insensitive matching."""

    def __init__(self, entries: Iterable[ModelEntry] = DEFAULT_ENTRIES) -> None:
        self._entries: dict[str, ModelEntry] = {}
        self._pattern: re.Pattern[str] | None = None
        self._alias_to_id: dict[str, str] = {}
        for entry in entries:
            self.add(entry)

    def add(self, entry: ModelEntry) -> None:
        """Add or replace an entry (keyed by model_id)."""
        self._entries[entry.model_id] = entry
        self._rebuild()

    def get(self, model_id: str) -> ModelEntry | None:
        return self._entries.get(model_id)

    def entries(self) -> list[ModelEntry]:
        return list(self._entries.values())

    def _rebuild(self) -> None:
        self._alias_to_id = {
            alias.lower(): entry.model_id
            for entry in self._entries.values()
            for alias in entry.aliases
        }
        # Longest first so "adobe firefly" wins over "firefly".
        aliases = sorted(self._alias_to_id, key=len, reverse=True)
        self._pattern = (
            re.compile(
                r"(?<![A-Za-z0-9])("
                + "|".join(re.escape(a) for a in aliases)
                + r")(?![A-Za-z0-9])",
                re.IGNORECASE,
            )
            if aliases
            else None
        )

    def find(self, text: str) -> list[tuple[ModelEntry, str]]:
        """Return (entry, matched alias) for each distinct entry in text."""
        if not self._pattern or not text:
            return []

        found: dict[str, tuple[ModelEntry, str]] = {}
        for match in self._pattern.finditer(text):
            alias = match.group(1).lower()
            model_id = self._alias_to_id[alias]
            found.setdefault(model_id, (self._entries[model_id], alias))
        return list(found.values())

    def resolve(self, signals: Iterable) -> list[ModelMatch]:
        """
        Resolve AISignal-like objects (kind, source, value) to matches.

        Only name-bearing signal kinds are resolved. Results are
        de-duplicated per (model, signal kind, signal source).
        """
        matches: dict[tuple[str, str, str], ModelMatch] = {}

        for signal in signals:
            if signal.kind not in _RESOLVABLE_SIGNAL_KINDS:
                continue
            for entry, alias in self.find(signal.value):
                key = (entry.model_id, signal.kind, signal.source)
                matches.setdefault(
                    key,
                    ModelMatch(
                        model_id=entry.model_id,
                        name=entry.name,
                        kind=entry.kind,
                        vendor=entry.vendor,
                        matched_alias=alias,
                        signal_kind=signal.kind,
                        signal_source=signal.source,
                    ),
                )

        return list(matches.values())


DEFAULT_REGISTRY = ModelRegistry()


def find_model(text: str) -> list[tuple[ModelEntry, str]]:
    """Look up known generator names in free text."""
    return DEFAULT_REGISTRY.find(text)


def resolve_signals(signals: Iterable) -> list[ModelMatch]:
    """Resolve AI signals against the default registry."""
    return DEFAULT_REGISTRY.resolve(signals)


__all__ = [
    "KIND_MODEL",
    "KIND_SERVICE",
    "KIND_TOOL",
    "KIND_VENDOR",
    "ModelEntry",
    "ModelMatch",
    "ModelRegistry",
    "DEFAULT_ENTRIES",
    "DEFAULT_REGISTRY",
    "find_model",
    "resolve_signals",
]
