# app/models/audio_job.py
from __future__ import annotations

import uuid
import datetime as dt

from app import db


def _uuid() -> str:
    return str(uuid.uuid4())


class AudioJob(db.Model):
    __tablename__ = "audio_jobs"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)

    user_id = db.Column(db.String(128), index=True, nullable=False, default="guest")

    filename = db.Column(db.String(255), nullable=True)
    language = db.Column(db.String(16), nullable=True, default="auto")
    language_detected = db.Column(db.String(16), nullable=True)

    status = db.Column(db.String(32), nullable=False, default="done")  # queued/processing/done/error

    duration_seconds = db.Column(db.Integer, nullable=True, default=0)

    transcript = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)  # tu UI usa string "summary" (no JSON aquí)

    error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: dt.datetime.utcnow())
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: dt.datetime.utcnow(), onupdate=lambda: dt.datetime.utcnow())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.id,
            "user_id": self.user_id,
            "filename": self.filename,
            "language": self.language,
            "language_detected": self.language_detected,
            "status": self.status,
            "duration_seconds": int(self.duration_seconds or 0),
            "transcript": self.transcript or "",
            "summary": self.summary or "",
            "error": self.error,
            "created_at": (self.created_at.isoformat() + "Z") if self.created_at else None,
        }

