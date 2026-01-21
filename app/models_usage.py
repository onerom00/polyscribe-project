# app/models_usage.py
from datetime import datetime
from app.extensions import db

class UsageLedger(db.Model):
    __tablename__ = "usage_ledger"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    delta_seconds = db.Column(db.Integer, nullable=False, default=0)
    job_id = db.Column(db.String(36))
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class UsageLedgerEvent(db.Model):
    __tablename__ = "usage_ledger_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    event_type = db.Column(db.String(32), nullable=False)  # 'debit' | 'credit'
    seconds = db.Column(db.Integer, nullable=False, default=0)
    job_id = db.Column(db.String(36))
    meta_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
