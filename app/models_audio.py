# app/models_audio.py
from __future__ import annotations
from datetime import datetime
from app.models import db

class AudioJob(db.Model):
    __tablename__ = "audio_jobs"

    id                = db.Column(db.String(36), primary_key=True)  # UUID string
    user_id           = db.Column(db.Integer, nullable=False)
    filename          = db.Column(db.String(512), nullable=False)
    original_filename = db.Column(db.String(512), nullable=False)
    audio_s3_key      = db.Column(db.String(512), default="")
    local_path        = db.Column(db.String(1024), default="")
    mime_type         = db.Column(db.String(128))
    size_bytes        = db.Column(db.Integer)

    language          = db.Column(db.String(32), default="auto")
    language_forced   = db.Column(db.Boolean, default=False)
    language_detected = db.Column(db.String(8))

    status            = db.Column(db.String(32), default="queued")  # queued|processing|completed|error
    error             = db.Column(db.Integer, default=0)
    error_message     = db.Column(db.Text)

    transcript        = db.Column(db.Text)
    summary           = db.Column(db.Text)
    duration_seconds  = db.Column(db.Integer)
    model_used        = db.Column(db.String(64))
    cost_cents        = db.Column(db.Integer)

    created_at        = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
