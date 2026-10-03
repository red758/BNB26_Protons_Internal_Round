"""
ModelLedger Evidence - Metadata

Reads embedded metadata with ExifTool and reduces its (often huge) raw
output to a small, stable, well-named structure.

This module ONLY collects metadata evidence.

It does NOT:
- decide whether content is authentic
- decide whether content was AI-generated
- assign a trust score
- produce the final ModelLedger verdict

What "clean" means here:
- Only useful fields are kept, under stable names, in fixed sections.
- Filesystem tags (path, modified/accessed times, permissions) are
  dropped. They describe the copy on disk, not the asset, and would
  make identical assets produce different evidence.
- Binary blobs (thumbnails, ICC data, MakerNotes payloads) are dropped.
- EXIF-style dates are converted to ISO 8601. A timezone is attached
  only when the file states one; otherwise the value stays naive.
- Long text is truncated; control characters are removed.
- GPS coordinates are NOT included unless include_gps=True. Whether a
  location exists is always reported (`location.gps_present`).

Metadata is trivially edited or stripped. Its absence proves nothing,
and its presence is a claim, not a fact.
"""

from __future__ import annotations

import functools
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT = 30
_MAX_TEXT = 500
_MAX_KEYWORDS = 25

# Groups ExifTool adds itself; they are not the file's embedded metadata.
_SYNTHETIC_GROUPS = frozenset({"ExifTool", "File", "Composite", "SourceFile"})

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_DATE_RE = re.compile(
    r"^(\d{4})[:\-](\d{2})[:\-](\d{2})[ T](\d{2}):(\d{2}):(\d{2})"
    r"(\.\d+)?\s*(Z|[+-]\d{2}:?\d{2})?$"
)
_OFFSET_RE = re.compile(r"^(Z|[+-]\d{2}:?\d{2})$")

_ORIENTATION = {
    1: "normal",
    2: "mirror horizontal",
    3: "rotate 180",
    4: "mirror vertical",
    5: "mirror horizontal, rotate 270 CW",
    6: "rotate 90 CW",
    7: "mirror horizontal, rotate 90 CW",
    8: "rotate 270 CW",
}
_COLOR_SPACE = {1: "sRGB", 2: "Adobe RGB", 65535: "Uncalibrated"}


class MetadataError(Exception):
    """Base exception for metadata errors."""


class MetadataFileNotFoundError(MetadataError):
    """Raised when the asset does not exist."""


class InvalidMetadataFileError(MetadataError):
    """Raised when the supplied path is not a regular file."""


class ExifToolNotFoundError(MetadataError):
    """Raised when the ExifTool binary cannot be found."""


class MetadataReadError(MetadataError):
    """Raised when ExifTool fails or returns unusable output."""


@dataclass(frozen=True)
class MetadataEvidence:
    """
    Clean metadata extracted from an asset.

    Every section is a dict containing only the fields that were found
    (missing fields are omitted, never filled with placeholders).

    Attributes:
        present:
            True if ExifTool extracted any tags from the file's own
            structures. This includes basic format info, so it does NOT
            mean EXIF/XMP exists; see `embedded` for that.

        file:        type, extension, mime_type, size_bytes
        image:       width, height, megapixels, orientation(+_label),
                     color_space, bit_depth, icc_profile
        camera:      make, model, lens, serial_number
        dates:       original, created, modified, metadata_modified
        exposure:    iso, f_number, exposure_time_s, focal_length_mm,
                     focal_length_35mm
        location:    gps_present (+ latitude, longitude, altitude_m
                     only when include_gps=True)
        software:    software, creator_tool, producer,
                     processing_software, history_agents
        provenance:  digital_source_type(+_uri), document_id,
                     original_document_id, instance_id
        authorship:  artist, copyright, credit, owner (self-declared)
        descriptions: title, description, comment, keywords
        media:       duration_s, frame_rate, video_codec, pages
        embedded:    has_exif/xmp/iptc/icc/maker_notes/thumbnail/c2pa
        groups:      embedded metadata groups ExifTool found
        raw_tag_count: size of the raw ExifTool output, for context
        warnings:    ExifTool warnings/errors for this file
        tool_name / tool_version: what produced this evidence
    """

    present: bool
    file: dict[str, Any] = field(default_factory=dict)
    image: dict[str, Any] = field(default_factory=dict)
    camera: dict[str, Any] = field(default_factory=dict)
    dates: dict[str, Any] = field(default_factory=dict)
    exposure: dict[str, Any] = field(default_factory=dict)
    location: dict[str, Any] = field(default_factory=dict)
    software: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    authorship: dict[str, Any] = field(default_factory=dict)
    descriptions: dict[str, Any] = field(default_factory=dict)
    media: dict[str, Any] = field(default_factory=dict)
    embedded: dict[str, bool] = field(default_factory=dict)
    groups: list[str] = field(default_factory=list)
    raw_tag_count: int = 0
    warnings: list[str] = field(default_factory=list)
    tool_name: str = "ExifTool"
    tool_version: str | None = None
    source: str = "ExifTool"


# --------------------------------------------------------------------- #
# ExifTool plumbing
# --------------------------------------------------------------------- #


def _find_exiftool(exiftool_path: str | Path | None) -> str:
    if exiftool_path is not None:
        candidate = str(exiftool_path)
        if shutil.which(candidate) or Path(candidate).is_file():
            return candidate
        raise ExifToolNotFoundError(f"ExifTool not found at: {candidate}")

    found = shutil.which("exiftool")
    if found is None:
        raise ExifToolNotFoundError(
            "ExifTool is not installed or not on PATH. "
            "See https://exiftool.org (e.g. 'apt install libimage-exiftool-perl' "
            "or 'brew install exiftool')."
        )
    return found


@functools.lru_cache(maxsize=8)
def _exiftool_version(binary: str) -> str | None:
    """Exact version string (read via -ver; JSON would turn 12.70 into 12.7)."""
    try:
        result = subprocess.run(
            [binary, "-ver"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    version = result.stdout.strip()
    return version or None


def get_exiftool_version(exiftool_path: str | Path | None = None) -> str | None:
    """Return the installed ExifTool version, or None if unavailable."""
    try:
        return _exiftool_version(_find_exiftool(exiftool_path))
    except ExifToolNotFoundError:
        return None


def _run_exiftool(binary: str, asset: Path, timeout: float) -> dict[str, Any]:
    # Absolute path: it can never be mistaken for an ExifTool option.
    command = [
        binary,
        "-json",
        "-G0",  # prefix tags with their family-0 group, e.g. "EXIF:Make"
        "-n",  # numeric values: decimal GPS, float exposure, int codes
        "-charset",
        "filename=utf8",
        str(asset),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise MetadataReadError(
            f"ExifTool timed out after {timeout}s on '{asset.name}'"
        ) from exc
    except OSError as exc:
        raise MetadataReadError(f"Unable to run ExifTool: {exc}") from exc

    try:
        data = json.loads(result.stdout)
    except ValueError:
        data = None

    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        detail = result.stderr.strip() or "no output"
        raise MetadataReadError(
            f"ExifTool returned no usable data for '{asset.name}': {detail}"
        )

    return data[0]


# --------------------------------------------------------------------- #
# value cleaning
# --------------------------------------------------------------------- #

# Filesystem tags are never read: they describe the copy, not the asset.


def _clean(value: Any) -> Any:
    """Normalize a raw ExifTool value; None means 'drop it'."""

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value

    if isinstance(value, str):
        text = _CONTROL_CHARS.sub("", value).strip()
        if not text or text.startswith("(Binary data"):
            return None
        if len(text) > _MAX_TEXT:
            text = text[:_MAX_TEXT] + "..."
        return text

    if isinstance(value, list):
        items = [_clean(item) for item in value]
        items = [item for item in items if item is not None]
        return items or None

    return None


def _get(tags: dict[str, Any], *keys: str) -> Any:
    """
    First available value among keys.

    A key is "Group:Tag". "*:Tag" matches the tag in any group.
    """

    for key in keys:
        if key.startswith("*:"):
            wanted = key[2:]
            for name, value in tags.items():
                if name.split(":", 1)[-1] == wanted:
                    return value
        elif key in tags:
            return tags[key]
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or None
    return str(value)


def _num(value: Any, digits: int | None = None) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = value
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
    else:
        return None
    return round(number, digits) if digits is not None else number


def _int(value: Any) -> int | None:
    number = _num(value)
    return int(number) if number is not None else None


def _iso(value: Any, offset: Any = None) -> str | None:
    """
    EXIF-style date -> ISO 8601.

    A timezone is attached only if the value or its offset tag states
    one. Zeroed dates ("0000:00:00 00:00:00") are treated as missing.
    """

    if not isinstance(value, str):
        return None

    match = _DATE_RE.match(value.strip())
    if match is None:
        return None

    year, month, day, hour, minute, second, fraction, zone = match.groups()
    if year == "0000" or month == "00" or day == "00":
        return None

    if zone is None and isinstance(offset, str) and _OFFSET_RE.match(offset):
        zone = offset

    if zone and zone != "Z" and ":" not in zone:
        zone = f"{zone[:3]}:{zone[3:]}"

    return (
        f"{year}-{month}-{day}T{hour}:{minute}:{second}"
        f"{fraction or ''}{zone or ''}"
    )


def _term(value: Any) -> str | None:
    text = _text(value)
    return text.rstrip("/").rsplit("/", 1)[-1] if text else None


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None and v != [] and v != ""}


# --------------------------------------------------------------------- #
# section builders
# --------------------------------------------------------------------- #


def _file_section(tags: dict[str, Any]) -> dict[str, Any]:
    extension = _text(_get(tags, "File:FileTypeExtension"))
    return _compact(
        {
            "type": _text(_get(tags, "File:FileType")),
            "extension": extension.lower() if extension else None,
            "mime_type": _text(_get(tags, "File:MIMEType")),
            "size_bytes": _int(_get(tags, "File:FileSize")),
        }
    )


def _image_section(tags: dict[str, Any]) -> dict[str, Any]:
    orientation = _int(_get(tags, "EXIF:Orientation"))
    color_space = _get(tags, "EXIF:ColorSpace")
    color_space_int = _int(color_space)

    return _compact(
        {
            "width": _int(
                _get(
                    tags, "File:ImageWidth", "PNG:ImageWidth",
                    "QuickTime:ImageWidth", "RIFF:ImageWidth",
                    "EXIF:ExifImageWidth", "*:ImageWidth",
                )
            ),
            "height": _int(
                _get(
                    tags, "File:ImageHeight", "PNG:ImageHeight",
                    "QuickTime:ImageHeight", "RIFF:ImageHeight",
                    "EXIF:ExifImageHeight", "*:ImageHeight",
                )
            ),
            "megapixels": _num(_get(tags, "Composite:Megapixels"), 2),
            "orientation": orientation,
            "orientation_label": _ORIENTATION.get(orientation)
            if orientation is not None
            else None,
            "color_space": _COLOR_SPACE.get(color_space_int, _text(color_space))
            if color_space is not None
            else None,
            "bit_depth": _int(_get(tags, "PNG:BitDepth", "File:BitsPerSample")),
            "icc_profile": _text(_get(tags, "ICC_Profile:ProfileDescription")),
        }
    )


def _camera_section(tags: dict[str, Any]) -> dict[str, Any]:
    return _compact(
        {
            "make": _text(_get(tags, "EXIF:Make", "QuickTime:Make", "XMP:Make")),
            "model": _text(_get(tags, "EXIF:Model", "QuickTime:Model", "XMP:Model")),
            "lens": _text(
                _get(tags, "EXIF:LensModel", "Composite:LensID", "*:LensModel")
            ),
            "serial_number": _text(
                _get(
                    tags, "EXIF:BodySerialNumber", "EXIF:SerialNumber",
                    "MakerNotes:SerialNumber",
                )
            ),
        }
    )


def _dates_section(tags: dict[str, Any]) -> dict[str, Any]:
    return _compact(
        {
            "original": _iso(
                _get(
                    tags, "EXIF:DateTimeOriginal", "XMP:DateTimeOriginal",
                    "XMP:DateCreated", "QuickTime:CreationDate",
                ),
                _get(tags, "EXIF:OffsetTimeOriginal"),
            ),
            "created": _iso(
                _get(
                    tags, "EXIF:CreateDate", "XMP:CreateDate",
                    "QuickTime:CreateDate", "PDF:CreateDate",
                    "PNG:CreationTime",
                ),
                _get(tags, "EXIF:OffsetTimeDigitized"),
            ),
            "modified": _iso(
                _get(
                    tags, "EXIF:ModifyDate", "XMP:ModifyDate",
                    "QuickTime:ModifyDate", "PDF:ModifyDate",
                ),
                _get(tags, "EXIF:OffsetTime"),
            ),
            "metadata_modified": _iso(_get(tags, "XMP:MetadataDate")),
        }
    )


def _exposure_section(tags: dict[str, Any]) -> dict[str, Any]:
    return _compact(
        {
            "iso": _int(_get(tags, "EXIF:ISO")),
            "f_number": _num(_get(tags, "EXIF:FNumber", "Composite:Aperture"), 2),
            "exposure_time_s": _num(_get(tags, "EXIF:ExposureTime"), 6),
            "focal_length_mm": _num(_get(tags, "EXIF:FocalLength"), 1),
            "focal_length_35mm": _num(
                _get(
                    tags, "EXIF:FocalLengthIn35mmFormat",
                    "Composite:FocalLength35efl",
                ),
                1,
            ),
        }
    )


def _location_section(tags: dict[str, Any], include_gps: bool) -> dict[str, Any]:
    latitude = _num(
        _get(tags, "Composite:GPSLatitude", "EXIF:GPSLatitude", "XMP:GPSLatitude")
    )
    longitude = _num(
        _get(tags, "Composite:GPSLongitude", "EXIF:GPSLongitude", "XMP:GPSLongitude")
    )

    present = (latitude is not None and longitude is not None) or any(
        name.endswith((":GPSCoordinates", ":GPSPosition")) for name in tags
    )

    section: dict[str, Any] = {"gps_present": present}

    if include_gps and latitude is not None and longitude is not None:
        section["latitude"] = round(latitude, 6)
        section["longitude"] = round(longitude, 6)
        altitude = _num(_get(tags, "Composite:GPSAltitude", "EXIF:GPSAltitude"), 1)
        if altitude is not None:
            section["altitude_m"] = altitude

    return section


def _software_section(tags: dict[str, Any]) -> dict[str, Any]:
    history = _get(tags, "XMP:HistorySoftwareAgent")
    if history is not None and not isinstance(history, list):
        history = [history]
    if isinstance(history, list):
        history = list(dict.fromkeys(str(item) for item in history))

    return _compact(
        {
            "software": _text(_get(tags, "EXIF:Software", "PNG:Software")),
            "creator_tool": _text(_get(tags, "XMP:CreatorTool", "PDF:Creator")),
            "producer": _text(_get(tags, "PDF:Producer")),
            "processing_software": _text(_get(tags, "EXIF:ProcessingSoftware")),
            "history_agents": history,
        }
    )


def _provenance_section(tags: dict[str, Any]) -> dict[str, Any]:
    uri = _text(_get(tags, "XMP:DigitalSourceType", "*:DigitalSourceType"))
    return _compact(
        {
            "digital_source_type": _term(uri),
            "digital_source_type_uri": uri,
            "document_id": _text(_get(tags, "XMP:DocumentID")),
            "original_document_id": _text(_get(tags, "XMP:OriginalDocumentID")),
            "instance_id": _text(_get(tags, "XMP:InstanceID")),
        }
    )


def _authorship_section(tags: dict[str, Any]) -> dict[str, Any]:
    return _compact(
        {
            "artist": _text(
                _get(
                    tags, "EXIF:Artist", "XMP:Creator", "IPTC:By-line",
                    "PDF:Author", "QuickTime:Artist", "*:Artist",
                )
            ),
            "copyright": _text(
                _get(
                    tags, "EXIF:Copyright", "XMP:Rights",
                    "IPTC:CopyrightNotice", "QuickTime:Copyright",
                )
            ),
            "credit": _text(_get(tags, "IPTC:Credit", "XMP:Credit")),
            "owner": _text(
                _get(tags, "EXIF:OwnerName", "EXIF:CameraOwnerName", "XMP:OwnerName")
            ),
        }
    )


def _descriptions_section(tags: dict[str, Any]) -> dict[str, Any]:
    keywords = _get(tags, "XMP:Subject", "IPTC:Keywords")
    if keywords is not None and not isinstance(keywords, list):
        keywords = [keywords]
    if isinstance(keywords, list):
        keywords = [str(k) for k in keywords][:_MAX_KEYWORDS]

    return _compact(
        {
            "title": _text(
                _get(
                    tags, "XMP:Title", "IPTC:ObjectName", "PDF:Title",
                    "QuickTime:Title",
                )
            ),
            "description": _text(
                _get(
                    tags, "EXIF:ImageDescription", "XMP:Description",
                    "IPTC:Caption-Abstract", "QuickTime:Description",
                )
            ),
            "comment": _text(
                _get(
                    tags, "EXIF:UserComment", "File:Comment", "PNG:Comment",
                    "XMP:UserComment",
                )
            ),
            "keywords": keywords,
        }
    )


def _media_section(tags: dict[str, Any]) -> dict[str, Any]:
    return _compact(
        {
            "duration_s": _num(
                _get(tags, "QuickTime:Duration", "Composite:Duration"), 3
            ),
            "frame_rate": _num(_get(tags, "QuickTime:VideoFrameRate"), 3),
            "video_codec": _text(_get(tags, "QuickTime:CompressorID")),
            "pages": _int(_get(tags, "PDF:PageCount")),
        }
    )


def _embedded_flags(groups: set[str], tags: dict[str, Any]) -> dict[str, bool]:
    return {
        "has_exif": "EXIF" in groups,
        "has_xmp": "XMP" in groups,
        "has_iptc": "IPTC" in groups,
        "has_icc": "ICC_Profile" in groups,
        "has_maker_notes": "MakerNotes" in groups,
        "has_thumbnail": any(
            name.startswith("EXIF:") and "Thumbnail" in name for name in tags
        ),
        "has_c2pa": "JUMBF" in groups
        and _text(tags.get("JUMBF:JUMDLabel")) == "c2pa",
    }


# --------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------- #


def clean_exiftool_output(
    raw: dict[str, Any],
    include_gps: bool = False,
) -> dict[str, Any]:
    """
    Reduce one raw ExifTool JSON object (-json -G0 -n) to the clean
    sections. Exposed separately so the cleaning is testable without
    ExifTool installed.

    Returns keyword arguments for MetadataEvidence (excluding tool info).
    """

    warnings = [
        str(raw[key])
        for key in ("ExifTool:Warning", "ExifTool:Error")
        if raw.get(key)
    ]

    tags: dict[str, Any] = {}
    for name, value in raw.items():
        if name == "SourceFile" or ":" not in name:
            continue
        cleaned = _clean(value)
        if cleaned is not None:
            tags[name] = cleaned

    groups = {name.split(":", 1)[0] for name in tags} - _SYNTHETIC_GROUPS

    return {
        "present": bool(groups),
        "file": _file_section(tags),
        "image": _image_section(tags),
        "camera": _camera_section(tags),
        "dates": _dates_section(tags),
        "exposure": _exposure_section(tags),
        "location": _location_section(tags, include_gps),
        "software": _software_section(tags),
        "provenance": _provenance_section(tags),
        "authorship": _authorship_section(tags),
        "descriptions": _descriptions_section(tags),
        "media": _media_section(tags),
        "embedded": _embedded_flags(groups, tags),
        "groups": sorted(groups),
        "raw_tag_count": sum(1 for name in raw if name != "SourceFile"),
        "warnings": warnings,
    }


def read_metadata(
    path: str | Path,
    include_gps: bool = False,
    exiftool_path: str | Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> MetadataEvidence:
    """
    Read and clean embedded metadata from an asset using ExifTool.

    Args:
        path: path to the asset.
        include_gps: include coordinates (default False; presence is
            always reported).
        exiftool_path: explicit ExifTool binary; defaults to PATH lookup.
        timeout: seconds before ExifTool is abandoned.

    Raises:
        MetadataFileNotFoundError: the asset does not exist.
        InvalidMetadataFileError: the path is not a regular file.
        ExifToolNotFoundError: ExifTool is not installed.
        MetadataReadError: ExifTool failed or returned nothing usable.
    """

    asset = Path(path)

    if not asset.exists():
        raise MetadataFileNotFoundError(f"Asset does not exist: {asset}")

    if not asset.is_file():
        raise InvalidMetadataFileError(
            f"Asset path is not a regular file: {asset}"
        )

    binary = _find_exiftool(exiftool_path)
    raw = _run_exiftool(binary, asset.resolve(), timeout)

    return MetadataEvidence(
        tool_version=_exiftool_version(binary),
        **clean_exiftool_output(raw, include_gps=include_gps),
    )


__all__ = [
    "ExifToolNotFoundError",
    "InvalidMetadataFileError",
    "MetadataError",
    "MetadataEvidence",
    "MetadataFileNotFoundError",
    "MetadataReadError",
    "clean_exiftool_output",
    "get_exiftool_version",
    "read_metadata",
]