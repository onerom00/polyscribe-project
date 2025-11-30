# app/models.py
from __future__ import annotations

import datetime as dt
from flask_sqlalchemy import SQLAlchemy

from app import db  # asegura que app/__init__.py crea 'db = SQLAlchemy(app)' o hace init_app(app)


def utcnow():
    return dt.datetime.utcnow()


class AudioJob(db.Model):
    __tablename__ = "audio_jobs"

    # CLAVE PRIMARIA CON AUTOINCREMENT
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # quién
    user_id = db.Column(db.Integer, nullable=True, index=True)

    # archivo
    filename = db.Column(db.String(255), nullable=True)             # nombre lógico (lo que muestras)
    original_filename = db.Column(db.String(255), nullable=True)    # evita NOT NULL
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

    # métricas / costos (opcionales)
    duration_seconds = db.Column(db.Integer, nullable=True)
    model_used = db.Column(db.String(64), nullable=True)
    cost_cents = db.Column(db.Integer, nullable=True)

    # timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<AudioJob id={self.id} user={self.user_id} status={self.status}>"
