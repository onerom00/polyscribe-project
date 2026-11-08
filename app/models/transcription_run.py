"""Provider executions retained independently of the existing AudioJob result."""
from __future__ import annotations

import datetime as dt
import uuid

from app.extensions import db


class TranscriptionRun(db.Model):
    __tablename__ = "transcription_runs"
    __table_args__ = (
        db.CheckConstraint("latency_ms >= 0", name="ck_run_latency_nonnegative"),
        db.CheckConstraint("cost_usd >= 0", name="ck_run_cost_nonnegative"),
        db.CheckConstraint(
            "language_confidence >= 0 AND language_confidence <= 1",
            name="ck_run_language_confidence",
        ),
        db.CheckConstraint(
            "overall_confidence >= 0 AND overall_confidence <= 1",
            name="ck_run_overall_confidence",
        ),
        db.Index(
            "uq_transcription_runs_selected_job", "job_id", unique=True,
            postgresql_where=db.text("is_selected = true"),
            sqlite_where=db.text("is_selected = 1"),
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = db.Column(
        db.String(36), db.ForeignKey("audio_jobs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    provider = db.Column(db.String(64), nullable=False)
    model = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="queued")
    error_message = db.Column(db.Text, nullable=True)
    language_detected = db.Column(db.String(16), nullable=True)
    language_confidence = db.Column(db.Float, nullable=True)
    overall_confidence = db.Column(db.Float, nullable=True)
    latency_ms = db.Column(db.Integer, nullable=True)
    cost_usd = db.Column(db.Numeric(12, 6), nullable=True)
    is_selected = db.Column(db.Boolean, nullable=False, default=False)
    transcript_text = db.Column(db.Text, nullable=True)
    raw_metadata = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow,
    )
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    job = db.relationship("AudioJob")
    segments = db.relationship(
        "TranscriptSegment", back_populates="transcription_run",
        cascade="all, delete-orphan", passive_deletes=True,
        order_by="TranscriptSegment.sequence",
    )
