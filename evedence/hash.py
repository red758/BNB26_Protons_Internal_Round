"""
ModelLedger Evidence - Cryptographic Hashing

Provides deterministic SHA-256 hashing for digital assets.
This module collects content-level evidence only.

It does not make authenticity or provenance decisions.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Union
import hashlib


PathLike = Union[str, Path]

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB


@dataclass(frozen=True)
class HashResult:
    """Cryptographic hash evidence for a digital asset."""

    algorithm: str
    digest: str
    size_bytes: int


class HashError(Exception):
    """Base exception for ModelLedger hashing errors."""


class FileNotFoundHashError(HashError):
    """Raised when the requested asset does not exist."""


class InvalidFileHashError(HashError):
    """Raised when the supplied path is not a regular file."""


def compute_sha256(
    path: PathLike,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> HashResult:
    """
    Compute the SHA-256 hash of a digital asset.

    The asset is read in chunks and is never modified.

    Args:
        path: Path to the asset.
        chunk_size: Number of bytes read per iteration.

    Returns:
        HashResult containing the algorithm, digest, and file size.

    Raises:
        FileNotFoundHashError: If the asset does not exist.
        InvalidFileHashError: If the path is not a regular file.
        ValueError: If chunk_size is invalid.
        HashError: If the asset cannot be read.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundHashError(
            f"Asset does not exist: {file_path}"
        )

    if not file_path.is_file():
        raise InvalidFileHashError(
            f"Asset path is not a regular file: {file_path}"
        )

    hasher = hashlib.sha256()
    size_bytes = 0

    try:
        with file_path.open("rb") as file:
            while True:
                chunk = file.read(chunk_size)

                if not chunk:
                    break

                hasher.update(chunk)
                size_bytes += len(chunk)

    except OSError as exc:
        raise HashError(
            f"Unable to read asset '{file_path}': {exc}"
        ) from exc

    return HashResult(
        algorithm="SHA-256",
        digest=hasher.hexdigest(),
        size_bytes=size_bytes,
    )


__all__ = [
    "HashResult",
    "HashError",
    "FileNotFoundHashError",
    "InvalidFileHashError",
    "compute_sha256",
]
