# app/models_payment.py
from __future__ import annotations

import datetime as dt

from app import db


def utcnow():
    return dt.datetime.utcnow()


class Payment(db.Model):
    """
    Registro de pagos (PayPal u otros).

    - user_id: usuario lógico (guest, email, uuid, etc.)
    - order_id: id de orden de PayPal (único)
    - sku: identificador del plan (p.ej. 'PLAN_60_MIN')
    - minutes: minutos acreditados con este pago
    - amount_usd: importe en USD (opcional, para reporte)
    - status: 'created', 'captured', 'refunded', etc.
    - raw_payload: JSON básico con los datos originales de PayPal
    """

    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    user_id = db.Column(db.String(255), nullable=False, index=True)
    order_id = db.Column(db.String(255), nullable=False, unique=True)

    sku = db.Column(db.String(255), nullable=True)
    minutes = db.Column(db.Integer, nullable=False, default=0)
    amount_usd = db.Column(db.Float, nullable=True)

    status = db.Column(db.String(32), nullable=False, default="created")

    # En SQLite JSON se mapea internamente a TEXT, no hay problema
    raw_payload = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} user_id={self.user_id} "
            f"order_id={self.order_id} minutes={self.minutes} status={self.status}>"
        )
