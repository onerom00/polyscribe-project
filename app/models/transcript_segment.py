"""Timed evidence belonging to one provider execution."""
from __future__ import annotations

import datetime as dt
import uuid

from app.extensions import db


class TranscriptSegment(db.Model):
    __tablename__ = "transcript_segments"
    __table_args__ = (
        db.UniqueConstraint(
            "transcription_run_id", "sequence", name="uq_segment_run_sequence",
        ),
        db.Index("ix_segment_run_start", "transcription_run_id", "start_seconds"),
        db.CheckConstraint("sequence >= 0", name="ck_segment_sequence_nonnegative"),
        db.CheckConstraint("start_seconds >= 0", name="ck_segment_start_nonnegative"),
        db.CheckConstraint("end_seconds >= start_seconds", name="ck_segment_time_order"),
        db.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_segment_confidence",
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transcription_run_id = db.Column(
        db.String(36), db.ForeignKey("transcription_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence = db.Column(db.Integer, nullable=False)
    start_seconds = db.Column(db.Float, nullable=False)
    end_seconds = db.Column(db.Float, nullable=False)
    speaker = db.Column(db.String(128), nullable=True)
    text = db.Column(db.Text, nullable=False)
    confidence = db.Column(db.Float, nullable=True)
    raw_metadata = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)

    transcription_run = db.relationship("TranscriptionRun", back_populates="segments")
