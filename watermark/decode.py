"""Decoding. Returns a validated watermark ID or None."""
from pathlib import Path

from PIL import Image, ImageOps

from watermark.embed import SUPPORTED_KINDS, UnsupportedMediaKind, get_trustmark
from watermark.id_generator import is_valid_id


def decode_watermark(src, kind: str):
    if kind not in SUPPORTED_KINDS:
        raise UnsupportedMediaKind(kind)
    return _decode_image(Path(src))


def _decode_image(src: Path):
    with Image.open(src) as im:
        img = ImageOps.exif_transpose(im).convert("RGB")
    secret, present, _schema = get_trustmark().decode(img, MODE="text")
    if not present:
        return None
    candidate = str(secret).strip().upper()
    return candidate if is_valid_id(candidate) else None  # drop decoder garbage