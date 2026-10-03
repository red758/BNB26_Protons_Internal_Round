"""Watermark IDs: 8 uppercase hex chars from a CSPRNG.

The ID is only a pointer. It never carries secrets or provenance.
"""
import re
import secrets

ID_LENGTH = 8
_ID_RE = re.compile(r"[0-9A-F]{8}")


def new_watermark_id() -> str:
    return secrets.token_hex(ID_LENGTH // 2).upper()


def is_valid_id(value) -> bool:
    return isinstance(value, str) and _ID_RE.fullmatch(value) is not None