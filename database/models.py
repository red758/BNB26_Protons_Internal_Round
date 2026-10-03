from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ImageRecord(Base):
    """One registered image. The watermark ID is the pointer to this row."""

    __tablename__ = "image_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watermark_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    media_kind: Mapped[str] = mapped_column(String(16), default="image")
    original_sha256: Mapped[str] = mapped_column(String(64), index=True)
    model_name: Mapped[str] = mapped_column(String(120))
    generator_name: Mapped[str] = mapped_column(String(120))
    creator: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict:
        """Keys match what the Jinja templates read."""
        return {
            "watermark_id": self.watermark_id,
            "filename": self.original_filename,
            "media_kind": self.media_kind,
            "sha256": self.original_sha256,
            "model_name": self.model_name,
            "generator_name": self.generator_name,
            "creator": self.creator,
            "description": self.description or "",
            "registered_at": self.created_at.strftime("%d %b %Y"),
        }


# Backwards-compatible name so provenance.py keeps working unchanged.
MediaRecord = ImageRecord