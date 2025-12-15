# app/models/audio_job.py
from __future__ import annotations

import datetime as dt
from app import db


class AudioJob(db.Model):
    __tablename__ = "audio_jobs"

    id = db.Column(db.String(36), primary_key=True)

    user_id = db.Column(db.String(255), nullable=False, index=True)

    status = db.Column(db.String(32), nullable=False, default="done", index=True)
    filename = db.Column(db.String(512), nullable=True)

    language = db.Column(db.String(16), nullable=True)            # idioma seleccionado
    language_detected = db.Column(db.String(16), nullable=True)   # idioma detectado

    duration_seconds = db.Column(db.Integer, nullable=True, default=0)

    transcript = db.Column(db.Text, nullable=True)

    # Si tu DB no soporta JSON nativo, SQLAlchemy lo guarda como TEXT en SQLite.
    # En Postgres será JSONB/JSON según config.
    summaries = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status,
            "filename": self.filename,
            "language": self.language,
            "language_detected": self.language_detected,
            "duration_seconds": int(self.duration_seconds or 0),
            "transcript": self.transcript,
            "summaries": self.summaries,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
