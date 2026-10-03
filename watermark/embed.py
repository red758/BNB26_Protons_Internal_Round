"""Embedding. One engine per media kind; only images are implemented."""
import threading
from pathlib import Path

from PIL import Image, ImageOps

from watermark.id_generator import is_valid_id

Image.MAX_IMAGE_PIXELS = 50_000_000  # reject decompression bombs

SUPPORTED_KINDS = {"image"}


class UnsupportedMediaKind(Exception):
    pass


_tm = None
_lock = threading.Lock()


def get_trustmark():
    """Load TrustMark once. The first call downloads model weights."""
    global _tm
    if _tm is None:
        with _lock:
            if _tm is None:
                from trustmark import TrustMark

                _tm = TrustMark(
                    verbose=False,
                    model_type="Q",
                    encoding_type=TrustMark.Encoding.BCH_5,
                )
    return _tm


def embed_watermark(src, kind: str, wm_id: str, out_dir) -> Path:
    """Write a watermarked copy of `src` into `out_dir` and return its path."""
    if kind not in SUPPORTED_KINDS:
        raise UnsupportedMediaKind(kind)
    if not is_valid_id(wm_id):
        raise ValueError("Invalid watermark ID")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return _embed_image(Path(src), wm_id, out_dir)


def _embed_image(src: Path, wm_id: str, out_dir: Path) -> Path:
    with Image.open(src) as im:
        cover = ImageOps.exif_transpose(im).convert("RGB")
    stego = get_trustmark().encode(cover, wm_id, MODE="text")
    out = out_dir / f"{wm_id}.png"  # lossless, so the first save doesn't weaken the mark
    stego.save(out, format="PNG")
    return out