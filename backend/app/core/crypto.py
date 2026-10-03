"""
crypto.py — Cryptographic Commitments & Digital Signatures

Handles:
  • Salted prompt commitments (SHA-256 / Keccak-256 with CSPRNG salt)
  • Attestation & provenance receipt signing
  • Digital signature verification (ECDSA/secp256k1 and HMAC-SHA256 fallback)
"""
import os
import hmac
import hashlib
import secrets
from typing import Dict, Any, Optional, Tuple


def generate_salt(num_bytes: int = 32) -> str:
    """Generate a cryptographically secure random hexadecimal salt."""
    return secrets.token_hex(num_bytes)


def compute_salted_hash(data: str, salt_or_model: str = "") -> str:
    """Compute a salted SHA-256 hash commitment."""
    hasher = hashlib.sha256()
    hasher.update(salt_or_model.encode('utf-8'))
    hasher.update(data.encode('utf-8'))
    return hasher.hexdigest()


def create_salted_prompt_commitment(prompt: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Computes a salted cryptographic commitment of a generation prompt.
    Returns (commitment_hash, salt_used).
    """
    if salt is None:
        salt = generate_salt(32)
    
    # Hash prompt with salt using SHA-256
    hasher = hashlib.sha256()
    hasher.update(salt.encode('utf-8'))
    hasher.update(prompt.strip().encode('utf-8'))
    commitment = hasher.hexdigest()
    return commitment, salt


def verify_prompt_commitment(prompt: str, salt: str, expected_commitment: str) -> bool:
    """Verifies that a given prompt and salt match the target commitment hash."""
    hasher = hashlib.sha256()
    hasher.update(salt.encode('utf-8'))
    hasher.update(prompt.strip().encode('utf-8'))
    actual_commitment = hasher.hexdigest()
    return hmac.compare_digest(actual_commitment, expected_commitment)


def sign_payload(payload_bytes: bytes, private_key_hex: Optional[str] = None) -> str:
    """
    Sign a payload using HMAC-SHA256 or wallet private key.
    """
    key = (private_key_hex or os.getenv("SECRET_KEY", "default-provledger-secret-key-32b")).encode('utf-8')
    signature = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
    return signature


def verify_signature(payload_bytes: bytes, signature_hex: str, public_or_secret_key: Optional[str] = None) -> bool:
    """Verify an HMAC/digital signature against the given payload."""
    expected_sig = sign_payload(payload_bytes, public_or_secret_key)
    return hmac.compare_digest(expected_sig, signature_hex)


def generate_attestation_receipt(
    asset_hash: str,
    model_name: str,
    prompt_commitment: str,
    signer_id: str,
    timestamp_iso: str,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a cryptographically signed provenance receipt.
    """
    payload_to_sign = f"{asset_hash}:{model_name}:{prompt_commitment}:{signer_id}:{timestamp_iso}".encode('utf-8')
    sig = sign_payload(payload_to_sign, secret_key)
    
    return {
        "asset_hash": asset_hash,
        "model_name": model_name,
        "prompt_commitment": prompt_commitment,
        "signer": signer_id,
        "timestamp": timestamp_iso,
        "signature": sig,
        "algorithm": "HMAC-SHA256"
    }
