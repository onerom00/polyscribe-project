# app/models_user.py
from __future__ import annotations

import datetime as dt
from app.extensions import db


def utcnow():
    return dt.datetime.utcnow()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(255), nullable=True)

    password_hash = db.Column(db.String(255), nullable=False)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)

    plan_tier = db.Column(db.String(32), nullable=False, default="free")

    # si luego quieres cuotas por user directo (opcional)
    minute_quota = db.Column(db.Integer, nullable=False, default=600)
    minutes_used = db.Column(db.Integer, nullable=False, default=0)

    paypal_subscription_id = db.Column(db.String(128), nullable=True)

    last_login_at = db.Column(db.DateTime, nullable=True)
    cycle_start = db.Column(db.DateTime, nullable=True)
    cycle_end = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} verified={self.is_verified}>"
