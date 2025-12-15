# app/models/audio_job.py
from __future__ import annotations

import datetime as dt
from app import db


class AudioJob(db.Model):
    __tablename__ = "audio_jobs"

    # IDs como string UUID
    id = db.Column(db.String(64), primary_key=True)

    # Multi-user (tu app lo usa)
    user_id = db.Column(db.String(128), index=True, nullable=False, default="guest")

    # Archivos / metadata
    filename = db.Column(db.String(255), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)
    audio_s3_key = db.Column(db.String(512), nullable=True)
    local_path = db.Column(db.String(512), nullable=True)
    mime_type = db.Column(db.String(128), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)

    # Idioma
    language = db.Column(db.String(16), nullable=True)  # 'auto', 'es', 'en', ...
    language_forced = db.Column(db.Integer, nullable=True, default=0)
    language_detected = db.Column(db.String(16), nullable=True)

    # Estado
    status = db.Column(db.String(32), nullable=True, default="done")  # queued/processing/done/error
    error = db.Column(db.Integer, nullable=True, default=0)
    error_message = db.Column(db.Text, nullable=True)

    # Contenido
    transcript = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)

    # Uso (para descontar)
    duration_seconds = db.Column(db.Integer, nullable=True, default=0)

    # Tracking (opcional)
    model_used = db.Column(db.String(64), nullable=True)
    cost_cents = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
