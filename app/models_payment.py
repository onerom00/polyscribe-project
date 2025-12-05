# app/models_payment.py
from __future__ import annotations

import datetime as dt
from typing import Any, Dict

from sqlalchemy.dialects.sqlite import JSON
from app import db


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=True, index=True)

    # No usamos plan_id para evitar el error; guardamos el SKU en plan_code
    plan_code = db.Column(db.String(64), nullable=True)  # ej: "starter_60"
    order_id = db.Column(db.String(128), nullable=True, unique=True)

    amount = db.Column(db.Float, nullable=False, default=0.0)
    currency = db.Column(db.String(8), nullable=False, default="USD")
    status = db.Column(db.String(32), nullable=False, default="captured")

    minutes = db.Column(db.Integer, nullable=False, default=0)

    raw_payload = db.Column(JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )


class PaymentEvent(db.Model):
    """
    Para guardar los webhooks de PayPal tal como llegan (opcional pero útil).
    """

    __tablename__ = "payment_events"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(128), nullable=False)
    raw_json = db.Column(JSON, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
