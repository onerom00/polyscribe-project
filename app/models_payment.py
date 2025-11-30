# app/models_payment.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app import db
from app.models import UsageLedger  # asegúrate de que el import coincide con tu models.py


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # en tu caso user_id es el correo tipo sb-xxx@personal.example.com
    user_id = db.Column(db.String(255), nullable=True)

    provider = db.Column(db.String(32), nullable=False, default="paypal")
    provider_id = db.Column(db.String(128), nullable=True)  # capture_id / order_id
    status = db.Column(db.String(32), nullable=False, default="CREATED")

    amount = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(8), nullable=True, default="USD")
    minutes = db.Column(db.Integer, nullable=True, default=0)

    raw_payload = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


def _get_or_create_usage(user_id: str) -> UsageLedger:
    usage = UsageLedger.query.filter_by(user_id=user_id).first()
    if not usage:
        usage = UsageLedger(
            user_id=user_id,
            allowance_seconds=0,
            used_seconds=0,
        )
        db.session.add(usage)
        db.session.flush()
    return usage


def credit_minutes(
    user_id: str,
    minutes: int,
    source: str = "paypal",
    plan_key: Optional[str] = None,
    raw_event: Optional[dict[str, Any]] = None,
    provider_id: Optional[str] = None,
    amount: Optional[float] = None,
    currency: str = "USD",
) -> None:
    """
    Acredita `minutes` minutos al usuario en UsageLedger y registra el pago.
    Se invoca desde el webhook de PayPal.
    """
    seconds = int(minutes) * 60

    usage = _get_or_create_usage(user_id)
    usage.allowance_seconds = (usage.allowance_seconds or 0) + seconds

    payment = Payment(
        user_id=user_id,
        provider="paypal",
        provider_id=provider_id,
        status="COMPLETED",
        amount=amount,
        currency=currency,
        minutes=minutes,
        raw_payload=str(raw_event)[:65535] if raw_event is not None else None,
    )
    db.session.add(payment)

    db.session.commit()
