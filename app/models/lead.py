# app/models/lead.py
from __future__ import annotations

import datetime as dt
from app import db

class Lead(db.Model):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=True)
    note = db.Column(db.String(500), nullable=True)

    user_id = db.Column(db.String(120), nullable=True, index=True)
    source = db.Column(db.String(80), nullable=True)   # e.g. "pricing", "home", "demo"

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: dt.datetime.utcnow())

    def as_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "note": self.note,
            "user_id": self.user_id,
            "source": self.source,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }
