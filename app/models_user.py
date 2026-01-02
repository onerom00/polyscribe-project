# app/models_user.py

from datetime import datetime
from app.extensions import db

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(255))
    password_hash = db.Column(db.String(255))

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=True)

    plan_tier = db.Column(db.String(32), nullable=False, default="free")
    minute_quota = db.Column(db.Integer, nullable=False, default=600)  # puedes ajustar
    minutes_used = db.Column(db.Integer, nullable=False, default=0)

    paypal_subscription_id = db.Column(db.String(128))

    last_login_at = db.Column(db.DateTime)
    cycle_start = db.Column(db.DateTime)
    cycle_end = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
