"""Verification: recover a watermark ID, then look up its record."""
from backend.services.provenance import get_record
from database.db import session_scope
from watermark.decode import decode_watermark


def verify_file(path, kind: str) -> dict:
    """Returns {state, watermark_id, record}. state is 'registered', 'orphan' or 'none'."""
    wm_id = decode_watermark(path, kind)
    if wm_id is None:
        return {"state": "none", "watermark_id": None, "record": None}

    with session_scope() as session:
        row = get_record(session, wm_id)
        record = row.to_dict() if row else None

    return {
        "state": "registered" if record else "orphan",
        "watermark_id": wm_id,
        "record": record,
    }