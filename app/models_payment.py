# app/models_payment.py
from __future__ import annotations

import datetime as dt

from app import db


def utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


class Payment(db.Model):
    """
    Registro de compras / suscripciones PayPal ligadas a un usuario de PolyScribe.
    """

    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)

    # normalmente el email con el que se identifica en PolyScribe
    user_id = db.Column(db.String(255), index=True, nullable=False)

    # código interno de tu plan (starter, pro, business...)
    plan_code = db.Column(db.String(50), nullable=False)

    # id de suscripción de PayPal (p.ej. I-XXXXXX), único
    paypal_subscription_id = db.Column(db.String(64), unique=True, nullable=False)

    status = db.Column(db.String(32), nullable=False, default="created")
    amount = db.Column(db.Numeric(10, 2), nullable=True)
    currency = db.Column(db.String(10), nullable=False, default="USD")

    # JSON crudo útil para debugging
    raw_payload = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover - solo para logs
        return (
            f"<Payment id={self.id} user={self.user_id} "
            f"plan={self.plan_code} status={self.status}>"
        )


class PaymentEvent(db.Model):
    """
    Histórico de webhooks/eventos de PayPal.
    """

    __tablename__ = "payment_events"

    id = db.Column(db.Integer, primary_key=True)

    payment_id = db.Column(
        db.Integer,
        db.ForeignKey("payments.id"),
        nullable=True,
        index=True,
    )

    event_type = db.Column(db.String(80), nullable=False)
    resource_id = db.Column(db.String(64), nullable=True)  # subscription_id etc
    raw_json = db.Column(db.JSON, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    payment = db.relationship("Payment", backref="events")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<PaymentEvent id={self.id} type={self.event_type} "
            f"resource={self.resource_id}>"
        )
