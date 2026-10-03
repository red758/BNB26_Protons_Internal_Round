"""Provenance records: allocate IDs, create and look up rows."""
from sqlalchemy import select

from database.models import ImageRecord
from watermark.id_generator import new_watermark_id


def reserve_id(session, tries: int = 10) -> str:
    for _ in range(tries):
        candidate = new_watermark_id()
        taken = session.scalar(select(ImageRecord.id).where(ImageRecord.watermark_id == candidate))
        if taken is None:
            return candidate
    raise RuntimeError("Could not allocate a unique watermark ID.")


def create_record(session, **fields) -> ImageRecord:
    record = ImageRecord(**fields)
    session.add(record)
    session.flush()
    return record


def get_record(session, watermark_id: str):
    return session.scalar(select(ImageRecord).where(ImageRecord.watermark_id == watermark_id))