import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

from . import db  # lo provee app/__init__.py

def _uuid() -> str:
    return str(uuid.uuid4())

class AudioJob(db.Model):
    __tablename__ = "audio_jobs"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.Integer, nullable=False, default=1)

    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    audio_s3_key = db.Column(db.String(512), nullable=False, default="")

    # ruta local donde se guardó el archivo
    local_path = db.Column(db.String(1024), nullable=True)

    mime_type = db.Column(db.String(64), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)

    language = db.Column(db.String(16), nullable=False, default="auto")
    language_forced = db.Column(db.Boolean, nullable=False, default=False)
    language_detected = db.Column(db.String(16), nullable=True)

    status = db.Column(db.String(32), nullable=False, default="queued")  # queued|processing|completed|failed
    error = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=True)

    transcript = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)

    duration_seconds = db.Column(db.Integer, nullable=True)
    model_used = db.Column(db.String(64), nullable=True)
    cost_cents = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def to_dict(self, full: bool = True) -> dict:
        """
        full=True => incluye transcript y summary
        """
        base = {
            "id": self.id,
            "user_id": self.user_id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "audio_s3_key": self.audio_s3_key or "",
            "local_path": self.local_path,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "language": self.language,
            "language_forced": bool(self.language_forced),
            "language_detected": self.language_detected,
            "status": self.status,
            "error": self.error,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "model_used": self.model_used,
            "cost_cents": self.cost_cents,
            "created_at": (self.created_at.isoformat() if self.created_at else None),
            "updated_at": (self.updated_at.isoformat() if self.updated_at else None),
        }
        if full:
            base["transcript"] = self.transcript
            base["summary"] = self.summary
        return base
