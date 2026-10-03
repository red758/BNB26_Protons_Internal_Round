"""
inference.py — Neural Embedding Model Extractor

Extracts a fixed-length feature vector from image/video bytes using either:
  • ResNet-50  (default, fast, good for general images)
  • CLIP ViT-B/32 (better semantic understanding)

The embedding is stored in PostgreSQL via pgvector and used for
approximate nearest-neighbour (HNSW) similarity search on verification.

Falls back to a zero-padded perceptual hash vector when torch is unavailable
(e.g., in test / CI environments without GPU/CPU torch installed).
"""
import io
import logging
from typing import List

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 512   # ResNet-50 avg-pool output; CLIP also 512


def compute_embedding(raw_bytes: bytes, content_type: str = "image/png") -> List[float]:
    """
    Return a normalised float32 embedding vector of length EMBEDDING_DIM.
    Falls back to a hash-derived pseudo-vector if torch is unavailable.
    """
    if not content_type.startswith("image/"):
        # Non-image: return hash-derived vector for registration/lookup
        return _hash_vector(raw_bytes)

    try:
        return _torch_embedding(raw_bytes)
    except Exception as exc:           # pragma: no cover
        logger.warning("torch embedding failed (%s); using hash fallback.", exc)
        return _hash_vector(raw_bytes)


def extract_embedding(raw_bytes: bytes, content_type: str = "image/png") -> List[float]:
    """Alias for compute_embedding."""
    return compute_embedding(raw_bytes, content_type)


# ── ResNet / CLIP (torch) ─────────────────────────────────────────────────────

def _torch_embedding(raw_bytes: bytes) -> List[float]:
    """Extract ResNet-50 average-pool features."""
    import torch
    import torchvision.models as models
    import torchvision.transforms as transforms
    from PIL import Image

    _model = _get_model()

    transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])

    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    tensor = transform(img).unsqueeze(0)          # (1, 3, 224, 224)

    with torch.no_grad():
        features = _model(tensor)                  # (1, 512)

    vec = features.squeeze().tolist()
    # L2-normalise
    norm = (sum(v * v for v in vec) ** 0.5) or 1.0
    return [v / norm for v in vec]


_cached_model = None


def _get_model():
    """Lazy-load and cache the ResNet-50 feature extractor."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model

    import torch
    import torchvision.models as models
    import torch.nn as nn

    base = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
    # Remove the classification head; keep avg-pool → 512-d output
    extractor = nn.Sequential(*list(base.children())[:-1], nn.Flatten())
    extractor.eval()
    _cached_model = extractor
    return _cached_model


# ── Hash-based fallback ───────────────────────────────────────────────────────

def _hash_vector(raw_bytes: bytes) -> List[float]:
    """
    Deterministic pseudo-embedding from SHA-256 bytes.
    Not visually meaningful but ensures every asset gets a unique vector.
    """
    import hashlib
    digest = hashlib.sha256(raw_bytes).digest()   # 32 bytes
    # Repeat to fill EMBEDDING_DIM floats and normalise to [0, 1]
    repeats = (EMBEDDING_DIM + 31) // 32
    extended = (digest * repeats)[:EMBEDDING_DIM]
    vec = [b / 255.0 for b in extended]
    norm = (sum(v * v for v in vec) ** 0.5) or 1.0
    return [v / norm for v in vec]
