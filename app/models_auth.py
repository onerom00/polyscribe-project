# app/models_auth.py
from __future__ import annotations

import datetime as dt
from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    name = db.Column(db.String(120), nullable=True)

    password_hash = db.Column(db.String(255), nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False, onupdate=dt.datetime.utcnow)


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
