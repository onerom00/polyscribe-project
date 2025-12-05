# app/models_payment.py
from __future__ import annotations

from datetime import datetime

from app import db


class Payment(db.Model):
    """
    Registro de pagos realizados (actualmente sólo PayPal).

    NOTA: No usar 'plan_id' aquí para evitar conflictos con la tabla existente.
    Usamos:
      - provider_order_id  -> ID de orden en PayPal
      - sku                -> código interno del plan (starter_60, pro_300, etc.)
      - minutes            -> minutos que se acreditan con el pago
    """
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)

    # Usuario dueño del saldo
    user_id = db.Column(db.String(255), nullable=False, index=True)

    # Proveedor de pago (paypal, stripe, etc.)
    provider = db.Column(db.String(50), nullable=False, default="paypal")

    # ID de la orden en el proveedor (en PayPal: order.id)
    provider_order_id = db.Column(db.String(255), nullable=False, unique=True)

    # SKU de nuestro plan (starter_60, pro_300, business_1200, etc.)
    sku = db.Column(db.String(64), nullable=True)

    # Minutos que se compran con este pago
    minutes = db.Column(db.Integer, nullable=False, default=0)

    # Monto pagado
    amount = db.Column(db.Float, nullable=False, default=0.0)

    # Moneda (USD, EUR, etc.)
    currency = db.Column(db.String(3), nullable=False, default="USD")

    # Estado: created, captured, failed, refunded...
    status = db.Column(db.String(32), nullable=False, default="created")

    # JSON crudo de PayPal o de la petición de captura
    raw_payload = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def mark_captured(self) -> None:
        self.status = "captured"
