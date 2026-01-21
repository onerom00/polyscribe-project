# app/models_payment.py
from __future__ import annotations
import datetime as dt
from app.extensions import db

def utcnow():
    return dt.datetime.utcnow()

class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # En PROD usaremos el id numérico de User convertido a string (ej: "12")
    user_id = db.Column(db.String(255), nullable=False, index=True)
    order_id = db.Column(db.String(255), nullable=False, unique=True)

    sku = db.Column(db.String(255), nullable=True)
    minutes = db.Column(db.Integer, nullable=False, default=0)
    amount_usd = db.Column(db.Float, nullable=True)

    status = db.Column(db.String(32), nullable=False, default="created")
    raw_payload = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} user_id={self.user_id} "
            f"order_id={self.order_id} minutes={self.minutes} status={self.status}>"
        )
