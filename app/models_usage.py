# app/models_usage.py
from __future__ import annotations
import datetime as dt
from app.extensions import db

def utcnow():
    return dt.datetime.utcnow()

class UsageLedger(db.Model):
    __tablename__ = "usage_ledger"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), index=True, nullable=False)

    delta_minutes = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(64), nullable=False)  # paypal, consume, bonus
    ref = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
