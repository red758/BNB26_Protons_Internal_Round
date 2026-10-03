"""Upload handling: sanitise the name, check extension and magic bytes, stream to disk, hash."""
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from werkzeug.utils import secure_filename

Image.MAX_IMAGE_PIXELS = 50_000_000


class UploadError(ValueError):
    """Message is safe to show to the user."""


@dataclass
class SavedUpload:
    path: Path
    filename: str
    kind: str
    sha256: str
    size: int


_MAGIC = {
    "png": lambda h: h.startswith(b"\x89PNG"),
    "jpg": lambda h: h.startswith(b"\xff\xd8\xff"),
    "jpeg": lambda h: h.startswith(b"\xff\xd8\xff"),
    "webp": lambda h: h[:4] == b"RIFF" and h[8:12] == b"WEBP",
    "wav": lambda h: h[:4] == b"RIFF" and h[8:12] == b"WAVE",
    "mp3": lambda h: h.startswith(b"ID3") or (len(h) > 1 and h[0] == 0xFF and (h[1] & 0xE0) == 0xE0),
    "flac": lambda h: h.startswith(b"fLaC"),
    "mp4": lambda h: h[4:8] == b"ftyp",
    "mov": lambda h: h[4:8] in (b"ftyp", b"moov", b"wide", b"mdat"),
    "webm": lambda h: h.startswith(b"\x1a\x45\xdf\xa3"),
    "pdf": lambda h: h.startswith(b"%PDF"),
}


def discard(path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def _kind_for(ext: str, allowed: dict):
    for kind, exts in allowed.items():
        if ext in exts:
            return kind
    return None


def save_upload(storage, upload_dir, allowed: dict) -> SavedUpload:
    name = secure_filename(storage.filename or "")
    if not name or "." not in name:
        raise UploadError("Choose a file with a valid name and extension.")
    ext = name.rsplit(".", 1)[1].lower()
    kind = _kind_for(ext, allowed)
    if kind is None:
        raise UploadError(f".{ext} files are not supported.")

    tmp_dir = Path(upload_dir) / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dest = tmp_dir / f"{uuid.uuid4().hex}.{ext}"  # never use the client's name on disk

    digest = hashlib.sha256()
    size = 0
    head = b""
    try:
        with open(dest, "wb") as out:
            while chunk := storage.stream.read(1 << 20):
                if not head:
                    head = chunk[:32]
                digest.update(chunk)
                size += len(chunk)
                out.write(chunk)

        if size == 0:
            raise UploadError("The file is empty.")
        if not _MAGIC[ext](head):
            raise UploadError(f"This file's contents don't match its .{ext} extension.")
        if kind == "image":
            try:
                with Image.open(dest) as im:
                    im.verify()
            except Exception:
                raise UploadError("This image could not be read.")
    except Exception:
        discard(dest)
        raise

    return SavedUpload(path=dest, filename=name, kind=kind, sha256=digest.hexdigest(), size=size)