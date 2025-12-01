# app/models.py
from __future__ import annotations

import datetime as dt

from app import db  # instancia global de SQLAlchemy creada en app/__init__.py


def utcnow():
    return dt.datetime.utcnow()


class AudioJob(db.Model):
    __tablename__ = "audio_jobs"

    # ID de job: usamos UUID en texto (como '8fc3ef0c-....')
    id = db.Column(db.String(64), primary_key=True)

    # quién (guest, email, id externo, etc.)
    user_id = db.Column(db.String(128), nullable=True, index=True)

    # archivo
    filename = db.Column(db.String(255), nullable=True)          # nombre lógico (lo que muestras)
    original_filename = db.Column(db.String(255), nullable=True) # nombre original
    audio_s3_key = db.Column(db.String(512), nullable=True, default="")
    local_path = db.Column(db.String(1024), nullable=True)
    mime_type = db.Column(db.String(120), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)

    # idiomas y estado
    language = db.Column(db.String(10), nullable=True, default="auto")
    language_forced = db.Column(db.Boolean, nullable=False, default=False)
    language_detected = db.Column(db.String(10), nullable=True)
    status = db.Column(db.String(32), nullable=True, default="done")
    error = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=True)

    # contenidos
    transcript = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)

    # métricas / costos
    duration_seconds = db.Column(db.Float, nullable=True)  # ahora FLOAT
    model_used = db.Column(db.String(64), nullable=True)
    cost_cents = db.Column(db.Integer, nullable=True)

    # timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<AudioJob id={self.id} user={self.user_id} status={self.status}>"
