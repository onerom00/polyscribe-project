# app/models_auth.py
from __future__ import annotations

import datetime as dt
from datetime import datetime

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(255), nullable=True)

    password_hash = db.Column(db.String(255), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)

    # (Opcional legacy; si ya no lo usas, puedes borrarlo luego con migración)
    verify_token = db.Column(db.String(128), index=True, nullable=True)
    verify_expires_at = db.Column(db.DateTime, nullable=True)

    # Plan / cuotas (puedes usarlo o ignorarlo si ya tienes Payment+usage ledger)
    plan_tier = db.Column(db.String(32), nullable=False, default="free")
    minute_quota = db.Column(db.Integer, nullable=False, default=600)
    minutes_used = db.Column(db.Integer, nullable=False, default=0)

    paypal_subscription_id = db.Column(db.String(128), nullable=True)

    last_login_at = db.Column(db.DateTime, nullable=True)
    cycle_start = db.Column(db.DateTime, nullable=True)
    cycle_end = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} verified={self.is_verified}>"


class EmailVerificationToken(db.Model):
    __tablename__ = "email_verification_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)

    token = db.Column(db.String(255), unique=True, index=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)

    token = db.Column(db.String(255), unique=True, index=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
