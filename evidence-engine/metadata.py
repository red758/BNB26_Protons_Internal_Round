
"""
ModelLedger Evidence - Digital Asset Metadata

Extracts metadata from digital assets without modifying the source file.

This module collects metadata evidence only.
It does not determine whether an asset is authentic,
AI-generated, or trustworthy.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

PathLike = Union[str, Path]


class MetadataError(Exception):
    """Base exception for ModelLedger metadata errors."""


class MetadataFileNotFoundError(MetadataError):
    """Raised when the requested asset does not exist."""


class InvalidMetadataFileError(MetadataError):
    """Raised when the supplied path is not a regular file."""


class MetadataExtractionError(MetadataError):
    """Raised when metadata cannot be extracted."""


@dataclass(frozen=True)
class MetadataRecord:
    """
    Structured metadata evidence extracted from a digital asset.

    The values are preserved as metadata evidence and are not treated
    as proof of authenticity by this module.
    """

    file_name: str
    file_extension: str
    mime_type: Optional[str]
    size_bytes: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    metadata_sources: List[str] = field(default_factory=list)


def _detect_mime_type(path: Path) -> Optional[str]:
    """
    Detect the MIME type using Python's standard library.
    """
    import mimetypes

    mime_type, _ = mimetypes.guess_type(path.name)
    return mime_type


def _extract_image_metadata(path: Path) -> Dict[str, Any]:
    """
    Extract common image metadata using Pillow when available.

    Pillow is intentionally imported lazily so that importing this
    module does not require Pillow unless image metadata extraction
    is actually requested.
    """

    try:
        from PIL import Image
    except ImportError:
        return {}

    metadata: Dict[str, Any] = {}

    try:
        with Image.open(path) as image:
            metadata["format"] = image.format
            metadata["mode"] = image.mode
            metadata["width"] = image.width
            metadata["height"] = image.height

            if image.info:
                for key, value in image.info.items():
                    metadata[f"info:{key}"] = _make_serializable(value)

            exif = image.getexif()

            if exif:
                exif_data: Dict[str, Any] = {}

                for tag_id, value in exif.items():
                    tag_name = _get_exif_tag_name(tag_id)
                    exif_data[tag_name] = _make_serializable(value)

                if exif_data:
                    metadata["exif"] = exif_data

    except Exception as exc:
        raise MetadataExtractionError(
            f"Unable to extract image metadata from '{path}': {exc}"
        ) from exc

    return metadata


def _get_exif_tag_name(tag_id: int) -> str:
    """Resolve an EXIF tag ID to its human-readable name."""

    try:
        from PIL.ExifTags import TAGS

        return str(TAGS.get(tag_id, tag_id))
    except ImportError:
        return str(tag_id)


def _make_serializable(value: Any) -> Any:
    """
    Convert common metadata values into JSON-compatible structures.

    Metadata may contain bytes, tuples, rational values, or other
    library-specific objects.
    """

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return value.hex()

    if isinstance(value, (list, tuple)):
        return [_make_serializable(item) for item in value]

    if isinstance(value, dict):
        return {
            str(key): _make_serializable(item)
            for key, item in value.items()
        }

    return str(value)


def extract_metadata(path: PathLike) -> MetadataRecord:
    """
    Extract available metadata from a digital asset.

    Supported metadata currently includes:
    - file name
    - file extension
    - MIME type
    - file size
    - image format
    - image dimensions
    - image information fields
    - EXIF metadata when available

    The original asset is opened read-only and is never modified.

    Args:
        path: Path to the digital asset.

    Returns:
        MetadataRecord containing the extracted metadata.

    Raises:
        MetadataFileNotFoundError:
            If the asset does not exist.

        InvalidMetadataFileError:
            If the path is not a regular file.

        MetadataExtractionError:
            If metadata extraction fails.
    """

    file_path = Path(path)

    if not file_path.exists():
        raise MetadataFileNotFoundError(
            f"Asset does not exist: {file_path}"
        )

    if not file_path.is_file():
        raise InvalidMetadataFileError(
            f"Asset path is not a regular file: {file_path}"
        )

    try:
        size_bytes = file_path.stat().st_size
    except OSError as exc:
        raise MetadataExtractionError(
            f"Unable to read asset information '{file_path}': {exc}"
        ) from exc

    mime_type = _detect_mime_type(file_path)

    metadata: Dict[str, Any] = {}
    metadata_sources: List[str] = ["filesystem"]

    if mime_type and mime_type.startswith("image/"):
        image_metadata = _extract_image_metadata(file_path)

        if image_metadata:
            metadata.update(image_metadata)

            if "exif" in image_metadata:
                metadata_sources.append("EXIF")

            metadata_sources.append("image-container")

    return MetadataRecord(
        file_name=file_path.name,
        file_extension=file_path.suffix.lower(),
        mime_type=mime_type,
        size_bytes=size_bytes,
        metadata=metadata,
        metadata_sources=metadata_sources,
    )


__all__ = [
    "MetadataRecord",
    "MetadataError",
    "MetadataFileNotFoundError",
    "InvalidMetadataFileError",
    "MetadataExtractionError",
    "extract_metadata",
]


