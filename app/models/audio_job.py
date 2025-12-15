# app/models/audio_job.py
from __future__ import annotations

import datetime as dt
import uuid

from app import db


class AudioJob(db.Model):
    __tablename__ = "audio_jobs"

    # ID tipo UUID string (estable en SQLite/Postgres)
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Usuario
    user_id = db.Column(db.String(128), nullable=False, index=True)

    # Archivo
    filename = db.Column(db.String(255), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)

    # Idiomas
    language = db.Column(db.String(16), nullable=True)           # seleccionado (auto/es/en/..)
    language_detected = db.Column(db.String(16), nullable=True)  # detectado por ASR

    # Estado
    status = db.Column(db.String(32), nullable=False, default="done")  # queued/processing/done/error
    error_message = db.Column(db.Text, nullable=True)

    # Resultados
    transcript = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)

    # Para cobro / minutos
    duration_seconds = db.Column(db.Integer, nullable=True)

    # Fechas
    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )
