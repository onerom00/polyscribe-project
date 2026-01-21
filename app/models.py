# app/models.py
from __future__ import annotations

import datetime as dt
import uuid

from app.extensions import db  # ✅ usa SIEMPRE app.extensions


def utcnow():
    return dt.datetime.utcnow()


def gen_job_id() -> str:
    """Genera un ID único de 32 caracteres hex para los jobs."""
    return uuid.uuid4().hex


# ---------------------------------------------------------
# ✅ IMPORTANTE:
# Antes existía aquí un class User(__tablename__="users")
# Eso DUPLICA la tabla 'users' porque el User oficial es app/models_user.py
# Para evitar el error:
#   sqlalchemy.exc.InvalidRequestError: Table 'users' is already defined
# Renombramos el modelo viejo a LegacyUser (y cambiamos la tabla).
# ---------------------------------------------------------
class LegacyUser(db.Model):
    __tablename__ = "legacy_users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<LegacyUser id={self.id} email={self.email}>"


# ---------------------------------------------------------
# JOBS DE TRANSCRIPCIÓN
# ---------------------------------------------------------
class AudioJob(db.Model):
    __tablename__ = "audio_jobs"

    id = db.Column(db.String(64), primary_key=True, nullable=False, default=gen_job_id)

    # quién
    user_id = db.Column(db.String(255), nullable=True, index=True)

    filename = db.Column(db.String(255), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)
    audio_s3_key = db.Column(db.String(512), nullable=True, default="")
    local_path = db.Column(db.String(1024), nullable=True)
    mime_type = db.Column(db.String(120), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)

    # idiomas y estado
    language = db.Column(db.String(10), nullable=True, default="auto")
    language_forced = db.Column(db.Boolean, nullable=False, default=False)
    language_detected = db.Column(db.String(10), nullable=True)

    status = db.Column(db.String(32), nullable=True, default="queued")
    error = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=True)

    # contenidos
    transcript = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)

    # métricas / costos (opcionales)
    duration_seconds = db.Column(db.Float, nullable=True)
    model_used = db.Column(db.String(64), nullable=True)
    cost_cents = db.Column(db.Integer, nullable=True)

    # timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<AudioJob id={self.id} user={self.user_id} status={self.status}>"
